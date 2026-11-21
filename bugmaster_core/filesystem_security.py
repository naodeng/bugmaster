"""Small filesystem checks shared by local persistence stores."""

import ctypes
import errno
import os
import sys


def _has_extended_acl(file_descriptor):
    """Return whether a descriptor has an extended ACL on macOS."""
    if sys.platform != "darwin":
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        get_acl = libc.acl_get_fd
        free_acl = libc.acl_free
    except (AttributeError, OSError) as error:
        raise OSError(errno.ENOSYS, "cannot inspect file access control list") from error
    get_acl.argtypes = [ctypes.c_int]
    get_acl.restype = ctypes.c_void_p
    free_acl.argtypes = [ctypes.c_void_p]
    free_acl.restype = ctypes.c_int
    ctypes.set_errno(0)
    acl = get_acl(file_descriptor)
    if not acl:
        error_number = ctypes.get_errno()
        if error_number == errno.ENOENT:
            return False
        if not error_number:
            error_number = errno.EIO
        raise OSError(error_number, os.strerror(error_number))
    try:
        return True
    finally:
        free_acl(acl)
