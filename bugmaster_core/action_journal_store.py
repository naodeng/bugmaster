"""Resolve append-only Action Journals from stable local identities."""

import hashlib
import os
import stat
from pathlib import Path

from .action_journal import (
    ActionJournal,
    JournalCorruptionError,
    JournalError,
    _nonempty,
)
from .filesystem_security import _has_extended_acl
from .session_store import SessionStore

_DIRECTORY_RELATIVE_IO_SUPPORTED = (
    os.name == "posix"
    and hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and os.open in os.supports_dir_fd
    and os.mkdir in os.supports_dir_fd
)


class ActionJournalStoreError(JournalError):
    """A Journal identity or its deterministic storage path is invalid."""


def _sync_directory(directory_fd):
    os.fsync(directory_fd)


def _normalize_storage_root(root):
    root_path = Path(os.path.abspath(os.fspath(root)))
    for alias, target in ((Path("/tmp"), "private/tmp"), (Path("/var"), "private/var")):
        try:
            relative_path = root_path.relative_to(alias)
        except ValueError:
            continue
        try:
            alias_stat = alias.lstat()
            target_path = os.readlink(alias)
        except OSError:
            return root_path
        if not stat.S_ISLNK(alias_stat.st_mode):
            return root_path
        if alias_stat.st_uid != 0 or target_path != target:
            raise ActionJournalStoreError(
                "storage root uses an untrusted system path alias"
            )
        return Path("/").joinpath(*Path(target).parts, *relative_path.parts)
    return root_path


def _reject_extended_acl(directory_fd, label):
    try:
        has_extended_acl = _has_extended_acl(directory_fd)
    except OSError as error:
        raise ActionJournalStoreError(
            "cannot verify access control for {}".format(label)
        ) from error
    if has_extended_acl:
        raise ActionJournalStoreError(
            "{} must not have an extended access control list".format(label)
        )


def _directory_flags():
    if not _DIRECTORY_RELATIVE_IO_SUPPORTED:
        raise ActionJournalStoreError(
            "secure directory-relative Journal storage is unsupported"
        )
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _require_private_directory(directory_fd, directory_stat, repair):
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise ActionJournalStoreError("Journal storage path is not a real directory")
    if directory_stat.st_uid != os.geteuid():
        raise ActionJournalStoreError("Journal storage directory has an unsafe owner")
    _reject_extended_acl(directory_fd, "Journal storage directory")
    if repair:
        if stat.S_IMODE(directory_stat.st_mode) != 0o700:
            try:
                os.fchmod(directory_fd, 0o700)
                _sync_directory(directory_fd)
            except OSError as error:
                raise ActionJournalStoreError(
                    "cannot secure Journal storage directory permissions"
                ) from error
    elif directory_stat.st_mode & (0o077 | 0o7000):
        raise ActionJournalStoreError(
            "Journal storage directory permissions are unsafe"
        )


def _require_trusted_ancestor(directory_stat):
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise ActionJournalStoreError("Journal storage ancestor is not a directory")
    if directory_stat.st_uid not in (0, os.geteuid()):
        raise ActionJournalStoreError("Journal storage ancestor has an unsafe owner")
    mode = directory_stat.st_mode
    if mode & 0o022 and not mode & stat.S_ISVTX:
        raise ActionJournalStoreError(
            "Journal storage ancestor is writable by another user"
        )


def _open_directory_at(parent_fd, name, *, create, private, repair):
    flags = _directory_flags()
    try:
        directory_fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            raise
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError as error:
            raise ActionJournalStoreError(
                "cannot create Journal storage directory"
            ) from error
        try:
            directory_fd = os.open(name, flags, dir_fd=parent_fd)
        except OSError as error:
            raise ActionJournalStoreError(
                "cannot securely open Journal storage directory"
            ) from error
    except OSError as error:
        raise ActionJournalStoreError(
            "cannot securely open Journal storage directory"
        ) from error

    try:
        directory_stat = os.fstat(directory_fd)
        if private:
            _require_private_directory(directory_fd, directory_stat, repair)
        else:
            _require_trusted_ancestor(directory_stat)
            _reject_extended_acl(directory_fd, "Journal storage ancestor")
        if create:
            try:
                _sync_directory(parent_fd)
            except OSError as error:
                raise ActionJournalStoreError(
                    "cannot synchronize Journal storage directory"
                ) from error
        return directory_fd
    except BaseException:
        os.close(directory_fd)
        raise


def _open_absolute_directory(path, *, create):
    flags = _directory_flags()
    try:
        directory_fd = os.open("/", flags)
    except OSError as error:
        raise ActionJournalStoreError(
            "cannot securely open Journal storage root"
        ) from error
    parts = path.parts[1:]
    if not parts:
        os.close(directory_fd)
        raise ActionJournalStoreError(
            "filesystem root cannot be Journal storage"
        )

    try:
        _require_trusted_ancestor(os.fstat(directory_fd))
        _reject_extended_acl(directory_fd, "Journal storage ancestor")
        for index, name in enumerate(parts):
            is_root = index == len(parts) - 1
            child_fd = _open_directory_at(
                directory_fd,
                name,
                create=create,
                private=is_root,
                repair=create and is_root,
            )
            os.close(directory_fd)
            directory_fd = child_fd
        return directory_fd
    except BaseException:
        os.close(directory_fd)
        raise


class ActionJournalStore:
    """Map one Session and Journal identity to a canonical local file.

    The mapping is ``<root>/journals/<sha256(sessionId)>/<sha256(journalId)>.jsonl``.
    It prevents callers of the reference validator from choosing an arbitrary
    file for a declared Journal ID. It does not authenticate local file content.
    """

    def __init__(self, root, session_id, journal_id):
        if not _nonempty(session_id):
            raise ActionJournalStoreError("session ID must be a non-empty string")
        if not _nonempty(journal_id):
            raise ActionJournalStoreError("journal ID must be a non-empty string")
        try:
            session_key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
            journal_key = hashlib.sha256(journal_id.encode("utf-8")).hexdigest()
        except UnicodeEncodeError as error:
            raise ActionJournalStoreError(
                "Journal identity is not valid UTF-8"
            ) from error
        input_root = Path(os.path.abspath(os.fspath(root)))
        self._root = input_root
        self._resolved_root = _normalize_storage_root(input_root)
        self._session_id = session_id
        self._journal_id = journal_id
        self._journals_dir = self._root / "journals"
        self._session_dir = self._journals_dir / session_key
        self._path = self._session_dir / (journal_key + ".jsonl")

    @property
    def path(self):
        """Return the deterministic path selected by this store's identities."""
        return self._path

    @property
    def root(self):
        """Return the storage root fixed when the store was constructed."""
        return self._root

    @property
    def session_id(self):
        """Return the Session identity fixed when the store was constructed."""
        return self._session_id

    @property
    def journal_id(self):
        """Return the Journal identity fixed when the store was constructed."""
        return self._journal_id

    def open(self):
        """Open an existing Journal through a pinned private directory."""
        return self._open_from_root_fd(None)

    def _open_from_root_fd(self, root_fd):
        try:
            if root_fd is None:
                directory_fd = self._open_store_directory(create=False)
            else:
                directory_fd = self._open_store_directory_at(root_fd, create=False)
        except FileNotFoundError as error:
            raise JournalCorruptionError(
                "canonical Journal storage path is missing"
            ) from error
        return ActionJournal(
            self.path,
            self.session_id,
            self.journal_id,
            require_existing=True,
            directory_fd=directory_fd,
        )

    def initialize(self):
        """Create before a Session revision exists, or reopen an existing Journal."""
        root_fd = self._open_root_directory(create=True)
        try:
            session_store = SessionStore(
                self._root, self._session_id, lambda _document: None
            )
            with session_store.lock_revision_snapshot(
                root_fd=root_fd
            ) as (revision_count, latest_session):
                session_exists = revision_count > 0
                if (
                    session_exists
                    and latest_session["journalId"] != self._journal_id
                ):
                    raise JournalCorruptionError(
                        "canonical Journal ID does not match the stored Session"
                    )
                try:
                    directory_fd = self._open_store_directory_at(
                        root_fd, create=not session_exists
                    )
                except FileNotFoundError as error:
                    if session_exists:
                        raise JournalCorruptionError(
                            "canonical Journal storage path is missing"
                        ) from error
                    raise ActionJournalStoreError(
                        "canonical Journal storage path disappeared during initialization"
                    ) from error
                if not session_exists:
                    try:
                        self._initialize_journal_file(directory_fd)
                    except BaseException:
                        os.close(directory_fd)
                        raise
                return ActionJournal(
                    self.path,
                    self.session_id,
                    self.journal_id,
                    require_existing=True,
                    directory_fd=directory_fd,
                )
        finally:
            os.close(root_fd)

    def _open_root_directory(self, *, create):
        """Open the configured root after validating its full ancestor chain."""
        return _open_absolute_directory(self._resolved_root, create=create)

    def _open_store_directory(self, *, create):
        root_fd = self._open_root_directory(create=create)
        try:
            return self._open_store_directory_at(root_fd, create=create)
        finally:
            os.close(root_fd)

    def _open_store_directory_at(self, root_fd, *, create):
        root_stat = os.fstat(root_fd)
        _require_private_directory(root_fd, root_stat, repair=False)
        journals_fd = _open_directory_at(
            root_fd,
            self._journals_dir.name,
            create=create,
            private=True,
            repair=create,
        )
        try:
            return _open_directory_at(
                journals_fd,
                self._session_dir.name,
                create=create,
                private=True,
                repair=create,
            )
        finally:
            os.close(journals_fd)

    def _initialize_journal_file(self, directory_fd):
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_NONBLOCK", 0)
        )
        created = False
        try:
            file_fd = os.open(
                self.path.name, flags, 0o600, dir_fd=directory_fd
            )
            created = True
        except FileExistsError:
            try:
                file_fd = os.open(
                    self.path.name,
                    os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
                    dir_fd=directory_fd,
                )
            except OSError as error:
                raise JournalCorruptionError(
                    "cannot safely open the existing canonical Journal"
                ) from error
        except OSError as error:
            raise ActionJournalStoreError(
                "cannot initialize canonical Journal"
            ) from error

        try:
            file_stat = os.fstat(file_fd)
            if not stat.S_ISREG(file_stat.st_mode):
                raise JournalCorruptionError(
                    "canonical journal path is not a regular file"
                )
            if file_stat.st_nlink != 1:
                raise JournalCorruptionError(
                    "canonical journal file must not be hard linked"
                )
            if file_stat.st_uid != os.geteuid():
                raise JournalCorruptionError(
                    "canonical journal file has an unsafe owner"
                )
            if not created and stat.S_IMODE(file_stat.st_mode) != 0o600:
                raise JournalCorruptionError(
                    "canonical journal file permissions are unsafe"
                )
            try:
                has_extended_acl = _has_extended_acl(file_fd)
            except OSError as error:
                raise JournalCorruptionError(
                    "canonical journal file access control cannot be verified"
                ) from error
            if has_extended_acl:
                raise JournalCorruptionError(
                    "canonical journal file must not have an extended access control list"
                )
            if created:
                os.fchmod(file_fd, 0o600)
            os.fsync(file_fd)
            _sync_directory(directory_fd)
        except OSError as error:
            raise ActionJournalStoreError(
                "cannot initialize canonical Journal"
            ) from error
        finally:
            os.close(file_fd)

    def _ensure_directories(self):
        """Create and secure all canonical directories before file creation."""
        directory_fd = self._open_store_directory(create=True)
        os.close(directory_fd)
