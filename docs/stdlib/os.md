# os Module Complexity

The `os` module is a thin layer over the operating system: most of its
functions are one syscall with argument marshalling around them.

A syscall counts as O(1) here. The kernel still resolves a path component by
component and a write still moves its bytes, but that cost is not what a
caller chooses between when picking one function over another. Where the
kernel's work does scale with an argument — a byte count, a buffer list, a
directory's contents, a flush — the row says so.

Size variables are named per row. The recurring pair is `n`, the number of
entries or components an operation handles, and `L`, the length of a path in
characters. Several rows need both, because a path's characters have to be
produced before anything can be done with them.

## Complexity Reference

### Path inspection

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.stat(path)` | O(1) | O(1) | One syscall, following symlinks |
| `os.lstat(path)` | O(1) | O(1) | Describes the link itself |
| `os.access(path, mode)` | O(1) | O(1) | `effective_ids=True` needs `os.supports_effective_ids` |
| `os.path.exists(path)` | O(1) | O(1) | One stat |
| `os.path.lexists(path)` | O(1) | O(1) | One lstat; true for a broken symlink |
| `os.path.isfile(path)` | O(1) | O(1) | One stat |
| `os.path.isdir(path)` | O(1) | O(1) | One stat |
| `os.path.islink(path)` | O(1) | O(1) | One lstat |
| `os.path.ismount(path)` | O(R) | O(R) | From 3.13 two lstat calls over O(L) of text; through 3.12 a `realpath()` of the parent runs first, carrying its cost |
| `os.path.getsize(path)` | O(1) | O(1) | One stat |
| `os.path.getatime(path)` | O(1) | O(1) | One stat |
| `os.path.getmtime(path)` | O(1) | O(1) | One stat |
| `os.path.getctime(path)` | O(1) | O(1) | Metadata change time on POSIX, creation time on Windows |
| `os.statvfs(path)` | O(1) | O(1) | Filesystem-wide counters |
| `os.fstatvfs(fd)` | O(1) | O(1) | |

### Directory listing and traversal

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.listdir(path)` | O(n) | O(n) | n = entries; every name is materialised |
| `os.scandir(path)` | O(n) | O(1) | n = entries over a full iteration; one entry is live at a time |
| `os.walk(path)` | O(n) | O(P) | n = entries visited, from 3.12; P = total length of the paths held at once. Through 3.11 each result is forwarded through one generator frame per level, so a chain of depth `d` costs O(n·d) |
| `os.fwalk(path)` | O(n) | O(P) | As `os.walk()`, and holds one open directory descriptor per level |

From 3.12 the traversal is one visit per entry, so the time column is `n`.
Through 3.11 it is not: `yield from` hands every result up through one
suspended frame per level, so walking a chain costs a factor of its depth on
top. That is the same rewrite that moved the space term, and it moves both.

The shape shows up in the clock even from 3.12, because the kernel resolves a
deeper path on every call and this page counts a syscall as O(1). At the same
entry count a deep tree is measurably slower than a wide one, and the bound
does not say so.

Space is a different story, and entry count does not bound it at all: what is
held is paths, not entries. Which shape costs the most depends on the version.

Through 3.11 `os.walk()` recurses once per level, suspending a frame that holds
that level's path, so depth dominates the peak there and a deep enough tree raises
`RecursionError` instead of finishing. From 3.12 it drives an explicit stack, so
for the default top-down walk breadth dominates instead and depth contributes
only the path being walked. `topdown=False` keeps each ancestor's result on that
stack until its descendants are done, which puts depth back into the peak.

### Creating, removing and linking

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.mkdir(path)` | O(1) | O(1) | One syscall; the parent must exist |
| `os.makedirs(path)` | O(n·L) | O(n·L) | n = components that do not exist yet, L = path length; it recurses down to the first existing head, each frame holding its own prefix, so enough *missing* components raise `RecursionError` |
| `os.rmdir(path)` | O(1) | O(1) | The directory must be empty |
| `os.removedirs(path)` | O(n·L) | O(L) | n = components it manages to remove; iterative, so one prefix is live at a time |
| `os.remove(path)` | O(1) | O(1) | |
| `os.unlink(path)` | O(1) | O(1) | The traditional Unix name; semantically identical to `os.remove()` |
| `os.rename(src, dst)` | O(1) | O(1) | Moves no bytes; fails across filesystems |
| `os.replace(src, dst)` | O(1) | O(1) | Overwrites `dst` |
| `os.renames(old, new)` | O(n·L) | O(n·L) | `makedirs()` on the new head, then `rename()`, then `removedirs()` on the old |
| `os.link(src, dst)` | O(1) | O(1) | |
| `os.symlink(src, dst)` | O(1) | O(1) | |
| `os.readlink(path)` | O(t) | O(t) | t = length of the stored target |
| `os.truncate(path, length)` | O(1) | O(1) | One syscall whatever `length` is |
| `os.ftruncate(fd, length)` | O(1) | O(1) | |
| `os.mkfifo(path)` | O(1) | O(1) | |
| `os.mknod(path)` | O(1) | O(1) | |
| `os.chmod(path, mode)` | O(1) | O(1) | |
| `os.fchmod(fd, mode)` | O(1) | O(1) | |
| `os.lchmod(path, mode)` | O(1) | O(1) | Where the platform has it; not on Linux |
| `os.chown(path, uid, gid)` | O(1) | O(1) | |
| `os.fchown(fd, uid, gid)` | O(1) | O(1) | |
| `os.lchown(path, uid, gid)` | O(1) | O(1) | Does not follow the link |
| `os.chflags(path, flags)` | O(1) | O(1) | BSD and macOS |
| `os.lchflags(path, flags)` | O(1) | O(1) | BSD and macOS |
| `os.utime(path, times)` | O(1) | O(1) | |
| `os.chroot(path)` | O(1) | O(1) | |

### File descriptors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.close(fd)` | O(1) | O(1) | |
| `os.closerange(fd_low, fd_high)` | O(k) | O(1) | k = `fd_high - fd_low`; every descriptor in the span is closed and none outside it. Where the platform lacks `close_range()` the fallback really does try each one |
| `os.dup(fd)` | O(1) | O(1) | |
| `os.dup2(fd, fd2)` | O(1) | O(1) | |
| `os.fdopen(fd, ...)` | O(1) | O(1) | Wraps the descriptor; reads nothing |
| `os.pipe()` | O(1) | O(1) | |
| `os.pipe2(flags)` | O(1) | O(1) | |
| `os.eventfd(initval)` | O(1) | O(1) | Linux |
| `os.eventfd_read(fd)` | O(1) | O(1) | |
| `os.eventfd_write(fd, value)` | O(1) | O(1) | |
| `os.memfd_create(name)` | O(1) | O(1) | Linux |
| `os.timerfd_create(clockid)` | O(1) | O(1) | Linux, 3.13+ |
| `os.timerfd_settime(fd, ...)` | O(1) | O(1) | |
| `os.timerfd_settime_ns(fd, ...)` | O(1) | O(1) | |
| `os.timerfd_gettime(fd)` | O(1) | O(1) | |
| `os.timerfd_gettime_ns(fd)` | O(1) | O(1) | |
| `os.pidfd_open(pid)` | O(1) | O(1) | Linux |
| `os.isatty(fd)` | O(1) | O(1) | |
| `os.get_blocking(fd)` | O(1) | O(1) | |
| `os.set_blocking(fd, blocking)` | O(1) | O(1) | |
| `os.get_inheritable(fd)` | O(1) | O(1) | |
| `os.set_inheritable(fd, inheritable)` | O(1) | O(1) | |
| `os.get_handle_inheritable(handle)` | O(1) | O(1) | Windows |
| `os.set_handle_inheritable(handle, inheritable)` | O(1) | O(1) | Windows |
| `os.fchdir(fd)` | O(1) | O(1) | |
| `os.lockf(fd, cmd, len)` | O(1) | O(1) | |
| `os.device_encoding(fd)` | O(1) | O(1) | `None` when the descriptor is not a terminal |

### Reading and writing descriptors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.read(fd, n)` | O(n) | O(n) | n = bytes requested; allocates the result |
| `os.readinto(fd, buffer)` | O(n) | O(1) | n = the buffer's size in bytes; fills the caller's buffer rather than allocating, 3.14+ |
| `os.readv(fd, buffers)` | O(n + k) | O(k) | n = total bytes, k = buffers; the vector itself costs per buffer |
| `os.pread(fd, n, offset)` | O(n) | O(n) | Does not move the file offset |
| `os.preadv(fd, buffers, offset)` | O(n + k) | O(k) | |
| `os.write(fd, data)` | O(n) | O(1) | n = bytes written |
| `os.writev(fd, buffers)` | O(n + k) | O(k) | n = total bytes, k = buffers |
| `os.pwrite(fd, data, offset)` | O(n) | O(1) | |
| `os.pwritev(fd, buffers, offset)` | O(n + k) | O(k) | |
| `os.lseek(fd, pos, whence)` | O(1) | O(1) | |
| `os.sendfile(out, in, offset, count)` | O(count) | O(1) | Copies in the kernel; no user-space buffer |
| `os.copy_file_range(src, dst, count)` | O(count) | O(1) | Same, within one filesystem |
| `os.splice(src, dst, count)` | O(count) | O(1) | Same, through a pipe |
| `os.posix_fadvise(fd, offset, len, advice)` | O(1) | O(1) | Advisory; the kernel may act later |
| `os.posix_fallocate(fd, offset, len)` | O(len) | O(1) | Reserves the blocks before returning |
| `os.fsync(fd)` | O(1) | O(1) | One syscall; blocks until the file's dirty data is written |
| `os.fdatasync(fd)` | O(1) | O(1) | As `fsync()`, skipping metadata that is not needed to read the data back |
| `os.sync()` | O(1) | O(1) | Blocks on every filesystem's dirty data |
| `os.urandom(size)` | O(size) | O(size) | |
| `os.getrandom(size)` | O(size) | O(size) | Linux |

### Terminals and pseudo-terminals

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.ctermid()` | O(1) | O(1) | |
| `os.ttyname(fd)` | O(n) | O(n) | n = length of the returned name |
| `os.get_terminal_size(fd)` | O(1) | O(1) | One `ioctl` |
| `os.tcgetpgrp(fd)` | O(1) | O(1) | |
| `os.tcsetpgrp(fd, pg)` | O(1) | O(1) | |
| `os.openpty()` | O(1) | O(1) | |
| `os.login_tty(fd)` | O(1) | O(1) | 3.11+ |
| `os.posix_openpt(oflag)` | O(1) | O(1) | 3.13+ |
| `os.grantpt(fd)` | O(1) | O(1) | 3.13+ |
| `os.unlockpt(fd)` | O(1) | O(1) | 3.13+ |
| `os.ptsname(fd)` | O(n) | O(n) | n = length of the returned name; 3.13+ |

### Process creation and exit

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.fork()` | O(1) | O(1) | Excluding registered handlers; the kernel's page-table copy scales with the parent's mappings |
| `os.forkpty()` | O(1) | O(1) | `fork()` plus a pty pair |
| `os.register_at_fork(...)` | O(1) | O(1) | Appends a handler; each `fork()` then pays for every handler registered, which is what the row above excludes |
| `os.execv(path, args)` | O(a) | O(a) | a = total bytes of the argument vector |
| `os.execve(path, args, env)` | O(a + e) | O(a + e) | e = total bytes of the environment |
| `os.execl(path, *args)` | O(a) | O(a) | Same, with the arguments spelled inline |
| `os.execle(path, *args, env)` | O(a + e) | O(a + e) | |
| `os.execvp(file, args)` | O(k·a + p) | O(a + p) | p = length of `PATH`, k = entries tried; every failed attempt marshals the arguments again |
| `os.execvpe(file, args, env)` | O(k·(a + e) + p) | O(a + e + p) | The environment is re-marshalled per attempt too |
| `os.execlp(file, *args)` | O(k·a + p) | O(a + p) | |
| `os.execlpe(file, *args, env)` | O(k·(a + e) + p) | O(a + e + p) | |
| `os.spawnv(mode, path, args)` | O(a) | O(a) | `fork()` plus the matching `exec` |
| `os.spawnve(mode, path, args, env)` | O(a + e) | O(a + e) | |
| `os.spawnl(mode, path, *args)` | O(a) | O(a) | |
| `os.spawnle(mode, path, *args, env)` | O(a + e) | O(a + e) | |
| `os.spawnvp(mode, file, args)` | O(k·a + p) | O(a + p) | |
| `os.spawnvpe(mode, file, args, env)` | O(k·(a + e) + p) | O(a + e + p) | |
| `os.spawnlp(mode, file, *args)` | O(k·a + p) | O(a + p) | |
| `os.spawnlpe(mode, file, *args, env)` | O(k·(a + e) + p) | O(a + e + p) | |
| `os.posix_spawn(path, argv, env)` | O(a + e + f) | O(a + e + f) | f = file actions |
| `os.posix_spawnp(file, argv, env)` | O(a + e + f + p) | O(a + e + f + p) | The PATH search happens in the C library, not per Python-level attempt |
| `os.popen(cmd)` | O(c) | O(c) | c = command length; starts a shell and returns a file object, the command runs concurrently |
| `os.system(cmd)` | Varies | O(c) | Runs `cmd` in a shell and blocks until it exits, so the time is the command's |
| `os.kill(pid, sig)` | O(1) | O(1) | |
| `os.killpg(pgid, sig)` | O(1) | O(1) | |
| `os.abort()` | O(1) | O(1) | Does not return |
| `os._exit(n)` | O(1) | O(1) | Skips cleanup; does not return |
| `os.startfile(path)` | O(1) | O(1) | Windows |

### Waiting and exit status

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.wait()` | O(1) | O(1) | One syscall; blocks until a child exits |
| `os.waitpid(pid, options)` | O(1) | O(1) | |
| `os.wait3(options)` | O(1) | O(1) | Also returns resource usage |
| `os.wait4(pid, options)` | O(1) | O(1) | |
| `os.waitid(idtype, id, options)` | O(1) | O(1) | |
| `os.waitstatus_to_exitcode(status)` | O(1) | O(1) | |
| `os.WIFEXITED(status)` | O(1) | O(1) | Bit test on an integer |
| `os.WEXITSTATUS(status)` | O(1) | O(1) | |
| `os.WIFSIGNALED(status)` | O(1) | O(1) | |
| `os.WTERMSIG(status)` | O(1) | O(1) | |
| `os.WCOREDUMP(status)` | O(1) | O(1) | |
| `os.WIFSTOPPED(status)` | O(1) | O(1) | |
| `os.WSTOPSIG(status)` | O(1) | O(1) | |
| `os.WIFCONTINUED(status)` | O(1) | O(1) | |

### Process attributes and priority

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.getpid()` | O(1) | O(1) | |
| `os.getppid()` | O(1) | O(1) | |
| `os.getcwd()` | O(L) | O(L) | L = length of the working directory |
| `os.getcwdb()` | O(L) | O(L) | Same, as bytes |
| `os.chdir(path)` | O(1) | O(1) | |
| `os.umask(mask)` | O(1) | O(1) | |
| `os.nice(increment)` | O(1) | O(1) | |
| `os.getpriority(which, who)` | O(1) | O(1) | |
| `os.setpriority(which, who, priority)` | O(1) | O(1) | |
| `os.times()` | O(1) | O(1) | |
| `os.getloadavg()` | O(1) | O(1) | |
| `os.uname()` | O(1) | O(1) | |
| `os.cpu_count()` | O(1) | O(1) | Machine-wide count |
| `os.process_cpu_count()` | O(c) | O(c) | Counts the affinity mask, so it carries `sched_getaffinity()`'s cost; 3.13+ |
| `os.plock(op)` | O(1) | O(1) | Where the platform has it |
| `os.setns(fd)` | O(1) | O(1) | Linux, 3.12+ |
| `os.unshare(flags)` | O(1) | O(1) | Linux, 3.12+ |

### User, group and session IDs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.getuid()` | O(1) | O(1) | |
| `os.geteuid()` | O(1) | O(1) | |
| `os.getgid()` | O(1) | O(1) | |
| `os.getegid()` | O(1) | O(1) | |
| `os.getresuid()` | O(1) | O(1) | |
| `os.getresgid()` | O(1) | O(1) | |
| `os.setuid(uid)` | O(1) | O(1) | |
| `os.seteuid(euid)` | O(1) | O(1) | |
| `os.setgid(gid)` | O(1) | O(1) | |
| `os.setegid(egid)` | O(1) | O(1) | |
| `os.setreuid(ruid, euid)` | O(1) | O(1) | |
| `os.setregid(rgid, egid)` | O(1) | O(1) | |
| `os.setresuid(ruid, euid, suid)` | O(1) | O(1) | |
| `os.setresgid(rgid, egid, sgid)` | O(1) | O(1) | |
| `os.getgroups()` | O(g) | O(g) | g = supplementary groups |
| `os.setgroups(groups)` | O(g) | O(g) | |
| `os.getgrouplist(user, group)` | Varies | O(g) | g = groups returned; consults the group database, see below |
| `os.initgroups(username, gid)` | Varies | O(g) | Same |
| `os.getlogin()` | O(n) | O(n) | n = login name; reads the terminal's login record |
| `os.getpgid(pid)` | O(1) | O(1) | |
| `os.getpgrp()` | O(1) | O(1) | |
| `os.setpgid(pid, pgrp)` | O(1) | O(1) | |
| `os.setpgrp()` | O(1) | O(1) | |
| `os.getsid(pid)` | O(1) | O(1) | |
| `os.setsid()` | O(1) | O(1) | |

`os.getgrouplist()` and `os.initgroups()` have no bound this page can state.
They resolve through the platform's name-service switch, so the cost belongs to
whichever backend is configured — a local file, a directory server over the
network, or a cache in front of either.

### Scheduling

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.sched_getaffinity(pid)` | O(c) | O(c) | c = the highest CPU id the mask spans, which sizes the bitmap; builds a set of the bits that are on |
| `os.sched_setaffinity(pid, mask)` | O(c) | O(c) | Same `c`: one high id costs as much as every lower one set |
| `os.sched_yield()` | O(1) | O(1) | |
| `os.sched_getscheduler(pid)` | O(1) | O(1) | |
| `os.sched_setscheduler(pid, policy, param)` | O(1) | O(1) | |
| `os.sched_getparam(pid)` | O(1) | O(1) | |
| `os.sched_setparam(pid, param)` | O(1) | O(1) | |
| `os.sched_get_priority_min(policy)` | O(1) | O(1) | |
| `os.sched_get_priority_max(policy)` | O(1) | O(1) | |
| `os.sched_rr_get_interval(pid)` | O(1) | O(1) | |

### Extended attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.getxattr(path, attribute)` | O(v) | O(v) | v = length of the stored value |
| `os.setxattr(path, attribute, value)` | O(v) | O(1) | |
| `os.listxattr(path)` | O(b) | O(b) | b = total bytes of the attribute names |
| `os.removexattr(path, attribute)` | O(1) | O(1) | |

### System configuration

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.sysconf(name)` | O(1) | O(1) | |
| `os.confstr(name)` | O(n) | O(n) | n = length of the returned string |
| `os.pathconf(path, name)` | O(1) | O(1) | |
| `os.fpathconf(fd, name)` | O(1) | O(1) | |
| `os.sysconf_names` | O(1) | O(1) | A dict; lookup, not a scan |
| `os.confstr_names` | O(1) | O(1) | A dict |
| `os.pathconf_names` | O(1) | O(1) | A dict |
| `os.supports_dir_fd` | O(1) | O(1) | A set; membership test |
| `os.supports_fd` | O(1) | O(1) | A set |
| `os.supports_follow_symlinks` | O(1) | O(1) | A set |
| `os.supports_effective_ids` | O(1) | O(1) | A set |
| `os.strerror(code)` | O(m) | O(m) | m = length of the message |
| `os.major(device)` | O(1) | O(1) | Arithmetic on the device number |
| `os.minor(device)` | O(1) | O(1) | |
| `os.makedev(major, minor)` | O(1) | O(1) | |
| `os.listdrives()` | O(k) | O(k) | k = drives; Windows, 3.12+ |
| `os.listvolumes()` | O(k) | O(k) | Windows, 3.12+ |
| `os.listmounts(volume)` | O(k) | O(k) | Windows, 3.12+ |
| `os.add_dll_directory(path)` | O(1) | O(1) | Windows |

### Environment

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.environ[key]` | O(k + v) | O(k + v) | k = key length, v = value length; a dict lookup in a snapshot taken at import. On POSIX the key is encoded and the value decoded around it; Windows stores `str` and hands it straight back |
| `os.environ.get(key, default)` | O(k + v) | O(k + v) | |
| `os.environ[key] = value` | O(k + v) | O(k + v) | Encodes both, then calls `putenv()`, so the `setenv()` scan below applies here too |
| `os.environ.items()` | O(1) | O(1) | A view; iterating it snapshots the keys, so consuming it is O(m) in time *and* space for m variables, plus the decoding |
| `os.environb` | O(k) | O(1) | The same mapping keyed by bytes; the key still has to be hashed, but nothing is encoded or decoded |
| `os.getenv(key)` | O(k + v) | O(k + v) | Reads `os.environ` |
| `os.getenvb(key)` | O(k) | O(1) | Reads `os.environb`; the value is handed back as stored, however long it is |
| `os.putenv(key, value)` | O(k + v) | O(k + v) | Changes the process environment, not `os.environ`; the C library's `setenv()` scans it, which a very large environment adds to |
| `os.unsetenv(key)` | O(k) | O(k) | Likewise, and `unsetenv()` scans it too |
| `os.reload_environ()` | O(b) | O(b) | b = total size of the environment, not just the variable count; rebuilds the snapshot, 3.14+ |
| `os.get_exec_path(env)` | O(p) | O(p) | p = length of `PATH` |

### Path manipulation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.path.join(path, *paths)` | O(L) | O(L) | L = total length of the arguments; a later absolute component discards the prefix but was still scanned |
| `os.path.split(path)` | O(L) | O(L) | |
| `os.path.dirname(path)` | O(L) | O(L) | |
| `os.path.basename(path)` | O(L) | O(L) | |
| `os.path.splitext(path)` | O(L) | O(L) | |
| `os.path.normpath(path)` | O(L) | O(L) | |
| `os.path.isabs(path)` | O(1) | O(1) | Inspects the prefix only; Windows before 3.13 rewrites separators across the whole path first, making it O(L) there |
| `os.path.normcase(path)` | O(L) | O(L) | O(1) on POSIX, which returns the argument unchanged; Windows case-folds it |
| `os.path.splitdrive(path)` | O(L) | O(L) | O(1) on POSIX, which returns the argument as the tail; a Windows UNC prefix is scanned and sliced |
| `os.path.splitroot(path)` | O(L) | O(L) | 3.12+; same shape as `splitdrive()` |
| `os.path.isreserved(path)` | O(L) | O(L) | Splits the path into components; Windows, 3.13+ |
| `os.path.relpath(path, start)` | O(L + S + C) | O(L + S + C) | S = length of `start`; one `getcwd()` per relative argument, so two when both are |
| `os.path.commonpath(paths)` | O(B) | O(B) | B = total length of every path given |
| `os.path.commonprefix(paths)` | O(B) | O(B) | Character-wise, so it can end mid-component |
| `os.path.expandvars(path)` | O(L + s) | O(L + s) | s = total length of the values substituted in |
| `os.path.expanduser(path)` | O(L + H) | O(L + H) | H = the home directory spliced in; `~user`, and a bare `~` with no `HOME` set, consult the password database at whatever that backend costs |
| `os.path.abspath(path)` | O(L + C) | O(L + C) | C = length of the working directory, which a relative path is prefixed with after one `getcwd()` |
| `os.path.realpath(path)` | O(R) | O(R) | R = the path text walked: the argument (rooted at the working directory if relative), plus every symlink target spliced into it; one lstat per component |
| `os.path.samefile(p1, p2)` | O(1) | O(1) | Two stat calls |
| `os.path.sameopenfile(fd1, fd2)` | O(1) | O(1) | |
| `os.path.samestat(s1, s2)` | O(1) | O(1) | Compares two `stat_result` objects |

Everything in this table is string work except seven: `ismount()`, `realpath()`,
`samefile()` and `sameopenfile()` always touch the filesystem; `abspath()` and
`relpath()` do so for a relative argument; and `expanduser()` consults the
password database for a `~user` prefix. `samestat()` only compares two results
that were fetched already.

`realpath()` is the one worth reading twice. Neither the argument's length nor
the result's bounds its cost: every symlink it resolves splices that link's
target into the path still to be walked, and those components are stat'ed in
turn. A two-component argument can cost more lstat calls than a sixteen-component
argument containing no links, and two arguments that resolve to the *same* path
can cost differently if one reaches it through a longer chain of links.

`normpath()` is the string-only alternative when the links do not matter.

### Filenames and path objects

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.fspath(path)` | O(1) | O(1) | Returns `str` and `bytes` arguments unchanged; anything else costs whatever its `__fspath__` does |
| `os.PathLike` | O(1) | O(1) | ABC; `isinstance()` checks for `__fspath__` |
| `os.fsencode(filename)` | O(n) | O(n) | Returns a `bytes` argument unchanged |
| `os.fsdecode(filename)` | O(n) | O(n) | Returns a `str` argument unchanged |

### DirEntry

`os.scandir()` yields `os.DirEntry` objects. Each one keeps the answers it has
already worked out, so the cost is in the first call — except for a stat that
failed, which is retried every time it is asked.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `DirEntry.name` | O(1) | O(1) | Carried on the entry |
| `DirEntry.path` | O(1) | O(1) | Built once, then cached |
| `DirEntry.is_dir()` | O(1) | O(1) | From the directory entry where the filesystem reports a type, else one stat, cached if it succeeds |
| `DirEntry.is_file()` | O(1) | O(1) | Same |
| `DirEntry.is_symlink()` | O(1) | O(1) | Same |
| `DirEntry.is_junction()` | O(1) | O(1) | 3.12+; always false on POSIX |
| `DirEntry.stat()` | O(1) | O(1) | One stat on POSIX, then cached; on Windows only a reparse point needs the call |
| `DirEntry.inode()` | O(1) | O(1) | From the directory entry where available, then cached |
| `os.scandir.close()` | O(1) | O(1) | Releases the directory handle; the `with` statement calls it |

### stat_result

Every field is one attribute read on a struct sequence.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stat_result.st_mode` | O(1) | O(1) | Type and permission bits |
| `stat_result.st_ino` | O(1) | O(1) | |
| `stat_result.st_dev` | O(1) | O(1) | |
| `stat_result.st_nlink` | O(1) | O(1) | |
| `stat_result.st_uid` | O(1) | O(1) | |
| `stat_result.st_gid` | O(1) | O(1) | |
| `stat_result.st_size` | O(1) | O(1) | Bytes, without reading the file |
| `stat_result.st_atime` | O(1) | O(1) | Float seconds, derived from the ns field |
| `stat_result.st_mtime` | O(1) | O(1) | |
| `stat_result.st_ctime` | O(1) | O(1) | |
| `stat_result.st_atime_ns` | O(1) | O(1) | Integer nanoseconds, without the float rounding |
| `stat_result.st_mtime_ns` | O(1) | O(1) | |
| `stat_result.st_ctime_ns` | O(1) | O(1) | |
| `stat_result.st_blocks` | O(1) | O(1) | |
| `stat_result.st_blksize` | O(1) | O(1) | |
| `stat_result.st_rdev` | O(1) | O(1) | |
| `stat_result.st_birthtime` | O(1) | O(1) | Where the platform records it |
| `stat_result.st_birthtime_ns` | O(1) | O(1) | 3.12+ |
| `stat_result.st_flags` | O(1) | O(1) | BSD and macOS |
| `stat_result.st_gen` | O(1) | O(1) | BSD |
| `stat_result.st_rsize` | O(1) | O(1) | macOS |
| `stat_result.st_creator` | O(1) | O(1) | macOS |
| `stat_result.st_type` | O(1) | O(1) | macOS |
| `stat_result.st_fstype` | O(1) | O(1) | Solaris |
| `stat_result.st_file_attributes` | O(1) | O(1) | Windows |
| `stat_result.st_reparse_tag` | O(1) | O(1) | Windows |

### statvfs_result

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `statvfs_result.f_bsize` | O(1) | O(1) | |
| `statvfs_result.f_frsize` | O(1) | O(1) | |
| `statvfs_result.f_blocks` | O(1) | O(1) | |
| `statvfs_result.f_bfree` | O(1) | O(1) | |
| `statvfs_result.f_bavail` | O(1) | O(1) | |
| `statvfs_result.f_files` | O(1) | O(1) | |
| `statvfs_result.f_ffree` | O(1) | O(1) | |
| `statvfs_result.f_favail` | O(1) | O(1) | |
| `statvfs_result.f_flag` | O(1) | O(1) | |
| `statvfs_result.f_namemax` | O(1) | O(1) | |
| `statvfs_result.f_fsid` | O(1) | O(1) | |

### terminal_size

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `terminal_size.columns` | O(1) | O(1) | |
| `terminal_size.lines` | O(1) | O(1) | |

### uname_result

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `uname_result.sysname` | O(1) | O(1) | |
| `uname_result.nodename` | O(1) | O(1) | |
| `uname_result.release` | O(1) | O(1) | |
| `uname_result.version` | O(1) | O(1) | |
| `uname_result.machine` | O(1) | O(1) | |

### sched_param

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sched_param(priority)` | O(1) | O(1) | |
| `sched_param.sched_priority` | O(1) | O(1) | |

## Listing a Directory

`os.listdir()` returns names and nothing else, so deciding what each one *is*
costs a stat per entry. `os.scandir()` carries the type the kernel already
reported, so for ordinary files and directories the same loop makes no extra
syscall.

```python
import os

# O(n) time, O(n) space - every name is materialised
files = os.listdir(".")

# ...and then one stat per name to classify it
only_files = [name for name in files if os.path.isfile(name)]

# O(n) time - the iterator holds one entry at a time, type included
with os.scandir(".") as entries:
    only_files = [entry.name for entry in entries if entry.is_file()]
```

The iterator is the O(1) part; the list comprehension above it is the caller's
O(n). The type comes from the directory entry itself where the filesystem
reports one. Two cases still cost a stat: a filesystem that reports no type, and
a symlink, which `is_file()` has to follow to answer about its target. A stat
that succeeds is cached on the entry, so asking again is free; one that fails —
a broken link, say — is retried on every call.

## Walking a Tree

```python
import os

# O(n) from 3.12; through 3.11 a deep walk also pays for its depth
for dirpath, dirnames, filenames in os.walk("."):
    for filename in filenames:
        path = os.path.join(dirpath, filename)  # O(L)

# Pruning by mutating dirnames in place skips a whole subtree
for dirpath, dirnames, filenames in os.walk("."):
    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
```

Where the depth lands in the peak depends on the version: before 3.12 it is a
suspended generator frame per level, each holding its own path, so a deep enough
tree raises `RecursionError` rather than finishing; from 3.12 only the queue of
entries waiting to be walked is held, and a wide directory is what fills it.

Pruning is the one change that removes work rather than moving it: assigning
into `dirnames` in place drops the subtree before the walk descends into it.

## Avoiding a Second Stat

Each of the stat-based `os.path` predicates makes its own syscall, so asking two
questions about a file that exists costs two stats. Asking once and handling the
failure costs one.

```python
import os

path = "data.txt"

# Two stat calls: one for exists(), one for getsize()
if os.path.exists(path) and os.path.getsize(path) > 0:
    pass

# One stat call, and no window between the check and the use
try:
    if os.path.getsize(path) > 0:
        pass
except FileNotFoundError:
    pass
```

The second form is also the one that is correct under concurrency: a file can
disappear between `exists()` and `getsize()`.

When several fields are wanted, take one `os.stat()` and read them off the
result — each field is an attribute read, not another syscall.

```python
import os
import stat

info = os.stat(".")                 # O(1), one syscall
size = info.st_size                 # O(1)
mtime = info.st_mtime_ns            # O(1)
is_directory = stat.S_ISDIR(info.st_mode)
```

## Building Paths Without Touching the Disk

```python
import os

path = os.path.join("home", "user", "documents", "file.txt")
dirname, filename = os.path.split(path)
# dirname = "home/user/documents"
# filename = "file.txt"

name, ext = os.path.splitext("file.txt")
# name = "file"
# ext = ".txt"

# O(1) on POSIX - only the prefix is inspected
os.path.isabs(path)

# O(L + C) and one getcwd() - C is the working directory it is joined to
absolute = os.path.abspath(path)
```

`os.path.realpath()` is the exception: it stats once per component it walks,
including the components of every symlink target it splices in along the way.
It is the wrong tool for normalising a string you never intend to open. Use
`normpath()` for that.

## Environment Variables

`os.environ` is a snapshot taken when `os` is imported, wrapped so that writes
reach the real process environment too. On POSIX a read is a dict lookup with
an encode of the key and a decode of the value around it, so a long value is not
free; Windows stores `str` and returns it as it is.

```python
import os

user = os.environ.get("USER", "unknown")   # O(k + v) - the value is decoded
os.environ["MY_VAR"] = "value"             # O(k + v), plus putenv()'s scan

# O(1) - a view, not a copy; the O(m) is in consuming it
pairs = os.environ.items()
count = sum(1 for _ in pairs)              # O(m), plus the text it decodes
```

`os.putenv()` changes the process environment without updating `os.environ`,
so a later `os.getenv()` will not see it. From 3.14, `os.reload_environ()`
rebuilds the snapshot, at the cost of the whole environment's text rather than
its variable count.

## Creating Directory Trees

```python
import os

# O(1) - the parent must already exist
os.mkdir("one")

# O(n·L) in both time and space - n is the components that do not exist yet
os.makedirs("one/two/three/four", exist_ok=True)

# O(n·L) time but O(L) space - it unwinds iteratively
os.removedirs("one/two/three/four")
```

`makedirs()` recurses down to the first head that already exists, and each
frame holds its own prefix of the path, which is why the space bound carries
both terms. Only the missing components count: one new directory under a
thousand-deep existing tree is a single frame, where a thousand missing ones
raise `RecursionError`. `removedirs()` unwinds the other way, keeping one
prefix live at a time.

## Version Notes

- **Python 3.5+**: `os.scandir()` and `os.DirEntry`, which is what lets a
  listing loop answer `is_file()` without a stat
- **Python 3.11+**: adds `os.login_tty()`
- **Python 3.12+**: `os.walk()` drives an explicit stack instead of recursing,
  so depth stops costing a suspended frame per level — in the peak, and in the
  time, since results no longer pass up through one frame per level. Adds
  `os.setns()`, `os.unshare()`, `os.path.splitroot()`,
  `DirEntry.is_junction()` and `stat_result.st_birthtime_ns`
- **Python 3.13+**: `os.path.ismount()` lstats the parent directly and keeps
  `realpath()` only as a fallback, so it stops scaling with the parent's
  depth; `os.path.isabs()` inspects a three-character prefix on Windows
  instead of rewriting separators across the whole path. Adds
  `os.process_cpu_count()`, the timerfd family, `os.posix_openpt()`,
  `os.grantpt()`, `os.unlockpt()`, `os.ptsname()` and `os.path.isreserved()`
- **Python 3.14+**: `os.readinto()` fills a caller-supplied buffer where
  `os.read()` allocates. Adds `os.reload_environ()`

## Platform Differences

- **POSIX**: the fork, exec, pty, scheduling, extended-attribute and
  supplementary-group families above
- **Linux**: `os.eventfd()`, `os.memfd_create()`, `os.timerfd_create()`,
  `os.pidfd_open()`, `os.getrandom()`, `os.splice()`, `os.copy_file_range()`,
  `os.setns()`, `os.unshare()`
- **Windows**: `os.startfile()`, `os.add_dll_directory()`, the handle
  inheritance functions, the drive and volume listings, and
  `os.path.isreserved()`. `os.path.normcase()` case-folds here and is O(L),
  where on POSIX it returns its argument unchanged
- **BSD and macOS**: `os.chflags()`, `os.lchflags()`, `os.lchmod()`, and the
  extra `stat_result` fields listed above

## Related Modules

- **[pathlib](pathlib.md)** - object-oriented paths over the same syscalls
- **[shutil](shutil.md)** - recursive copies and removals
- **[glob](glob.md)** - pattern expansion over directory listings
- **[tempfile](tempfile.md)** - temporary files and directories
- **[subprocess](subprocess.md)** - the supported way to start a process
- **[stat](stat.md)** - interpreting `st_mode`

## Best Practices

✅ **Do**:

- Use `os.scandir()` over `os.listdir()` when the loop asks what each entry is
- Take one `os.stat()` and read several fields off the result
- Open or stat and handle the failure, rather than testing first and then
  acting on the answer
- Prune `os.walk()` by assigning into `dirnames[:]`, which skips the subtree
  instead of filtering its results
- Use `os.path.join()` and `os.fspath()` rather than string concatenation

❌ **Avoid**:

- A predicate per question when one `os.stat()` answers all of them
- `os.path.realpath()` where `os.path.normpath()` will do
- `os.makedirs()` on a path with enough missing components to exhaust the recursion limit
- `os.putenv()` when `os.environ[key] = value` is what you meant
- Materialising `os.listdir()` for a directory you only iterate once
