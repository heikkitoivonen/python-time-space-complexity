# subprocess Module Complexity

The `subprocess` module starts operating-system processes and connects to their standard streams. Two costs in every call are not the module's: the spawn itself, and the time the child runs. The rows below price what the module does around those - what it encodes, copies, polls and buffers - and say which calls can block on a pipe that has filled. They describe POSIX: on Windows `Popen()` is one `CreateProcess` call, `shell=True` runs `cmd.exe`, and `terminate()` and `kill()` both end the process outright. The examples use POSIX utilities.

## Complexity Reference

Size variables: s = one spawn, a fork or `posix_spawn` of the caller and an exec, w = time spent blocked on the child, a = the arguments, their number and total length, e = the total length of the environment encoded for the child, p = descriptors in `pass_fds`, g = entries in `extra_groups`, P = the total length of the candidate paths built from `PATH` when the program is given without a directory, k = `Popen` objects collected before their child was waited for, i = input bytes, o = output bytes captured from stdout and stderr together, c = characters in a command line, f = the caller's own function, whose time and space are its own, S = the cost of one `Popen()` call, the first row, in whichever column it appears.

### Popen

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Popen()` | O(a + e + p log p + g + k + P + s + f) | O(a + e + p + g + k + P + f) | Encodes the arguments and an explicit `env` - `env=None` inherits the caller's, which Python 3.10 to 3.12 encode as well when they spawn through `posix_spawn` -, builds one candidate path per `PATH` directory for a program given without one, sorts `pass_fds`, lists `extra_groups`, resolving a name given for `user`, `group` or a group through the account database, polls the k children dropped unwaited through a copy of their list, then spawns; the child tries the candidates in turn until one exec succeeds, so a full path removes the P term. `shell=True` runs a `str` through `sh -c`; without it a `str` is the program's name, not split. `close_fds=True`, the default, closes every descriptor above 2 in the child except `pass_fds`, at the platform's cost for closing them; `close_fds=False` passes on only those marked inheritable. `preexec_fn`, f, runs in the child between the fork and the exec |
| `Popen.args/pid/returncode/stdin/stdout/stderr/encoding/errors/text_mode/pipesize/universal_newlines` | O(1) | O(1) | `args` is the object passed, not a copy; `returncode` is None until the exit has been collected; `universal_newlines` is another name for `text_mode` |
| `Popen.communicate()` | O(i + o + w) | O(i + o) | Writes the input in chunks while reading both output pipes, so no pipe stays full waiting on the parent; text mode encodes the input and decodes the output once each. A `timeout` that expires raises TimeoutExpired carrying the output so far and leaves the child running; a later call carries on without losing any of it, but may not be given input |
| `Popen.wait()` | O(w) | O(1) | Immediate once the exit has been collected; a `timeout` that expires raises TimeoutExpired with the child still running |
| `Popen.poll()` | O(1) | O(1) | One non-blocking check, setting `returncode` once the child has exited |
| `Popen.send_signal()` / `Popen.terminate()` / `Popen.kill()` | O(1) | O(1) | Poll first and send nothing to a child whose exit is already collected; SIGTERM and SIGKILL are sent and not waited for, so a child that ignores SIGTERM is still running when `terminate()` returns |
| `Popen.__exit__()` (with-statement exit) | O(w) | O(1) | Closes the parent's ends of the pipes, flushing what is buffered for stdin, then `wait()`; output not read by then is gone, and a child still writing to a closed pipe fails |

### run() and CompletedProcess

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `run()` | O(S + i + o + w) | O(S + i + o) | `Popen()` then `communicate()`; `capture_output=True` and `input=` add the pipes. A `timeout` that expires kills the child, collects it and raises TimeoutExpired carrying the output so far; `check=True` raises CalledProcessError carrying the output |
| `CompletedProcess()` / `CompletedProcess.args/returncode/stdout/stderr` | O(1) | O(1) | Holds what `run()` collected; `stdout` and `stderr` are None unless captured |
| `CompletedProcess.check_returncode()` | O(1) | O(1) | Raises CalledProcessError on a non-zero code, holding `stdout` and `stderr` by reference, not copied |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `call()` / `check_call()` | O(S + w) | O(S) | `Popen()` then `wait()`, nothing read: a stream set to `PIPE` fills at the pipe's capacity and the child blocks on it, until a `timeout` kills it or for good. `check_call()` raises CalledProcessError on a non-zero code |
| `check_output()` | O(S + i + o + w) | O(S + i + o) | `run()` with stdout captured and `check=True`, returning stdout alone; stderr is not captured unless asked for |
| `getstatusoutput()` / `getoutput()` | O(S + o + w) | O(S + o) | `check_output()` through the shell, stderr merged into stdout, decoded as text; one trailing newline is stripped |
| `list2cmdline()` | O(c) | O(c) | Quotes and joins the arguments by the Windows C runtime's rules, what `Popen()` does to a list on Windows |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `PIPE` / `STDOUT` / `DEVNULL` | O(1) | O(1) | `PIPE` opens one pipe per stream, of `pipesize` bytes where the platform allows a size; `STDOUT` sends stderr wherever stdout goes; `DEVNULL` opens `os.devnull` once per `Popen()` however many streams use it |

### SubprocessError, CalledProcessError and TimeoutExpired

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SubprocessError` / `CalledProcessError` / `TimeoutExpired` | O(1) | O(1) | The last two subclass the first |
| `CalledProcessError.returncode/cmd/output/stdout/stderr` | O(1) | O(1) | `stdout` is another name for `output`; both hold the captured object, not a copy |
| `TimeoutExpired.cmd/timeout/output/stdout/stderr` | O(1) | O(1) | `stdout` is another name for `output` |

### Windows

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `STARTUPINFO()` / `CREATE_NEW_CONSOLE` / `CREATE_NEW_PROCESS_GROUP` / `CREATE_NO_WINDOW` / `CREATE_DEFAULT_ERROR_MODE` / `CREATE_BREAKAWAY_FROM_JOB` / `DETACHED_PROCESS` / `STARTF_USESTDHANDLES` / `STARTF_USESHOWWINDOW` / `STARTF_FORCEONFEEDBACK` / `STARTF_FORCEOFFFEEDBACK` / `STD_INPUT_HANDLE` / `STD_OUTPUT_HANDLE` / `STD_ERROR_HANDLE` / `SW_HIDE` / `ABOVE_NORMAL_PRIORITY_CLASS` / `BELOW_NORMAL_PRIORITY_CLASS` / `HIGH_PRIORITY_CLASS` / `IDLE_PRIORITY_CLASS` / `NORMAL_PRIORITY_CLASS` / `REALTIME_PRIORITY_CLASS` | O(1) | O(1) | Windows only: `STARTUPINFO()` and the constants for `Popen()`'s `startupinfo` and `creationflags` arguments, plus the three standard handle ids; `STARTF_FORCEONFEEDBACK` and `STARTF_FORCEOFFFEEDBACK` are Python 3.13+ |

A pipe holds a bounded number of bytes, the platform's. A child that writes more than that to a pipe nobody is reading blocks on the write until someone does, which is why `communicate()` and `run()` read stdout and stderr together, and why reading one of them to the end yourself while the other fills waits for good.

## Basic Usage

```python
import subprocess

# Run and wait; nothing is captured - O(S + w)
result = subprocess.run(["true"])
print(result.returncode)  # 0

# Capture both streams - O(S + o + w)
result = subprocess.run(["echo", "hello"], capture_output=True, text=True)
print(repr(result.stdout))  # 'hello\n'

# A non-zero exit is a value unless check=True
result = subprocess.run(["false"])  # O(S + w)
if result.returncode != 0:  # O(1)
    print("Command failed")
```

## Process Communication

```python
import subprocess

# Send input, capture output - O(S + i + o + w)
result = subprocess.run(
    ["wc", "-w"],
    input="hello wide world\n",
    text=True,
    capture_output=True,
)
print(result.stdout.strip())  # 3

# check=True turns the exit code into an exception - O(1) on top
try:
    subprocess.run(["false"], check=True)
except subprocess.CalledProcessError as error:
    print(error.returncode)  # 1
```

## Popen for Advanced Control

```python
import subprocess

process = subprocess.Popen(  # O(S)
    ["cat"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)
print(process.poll())  # None - O(1), the child is still running

# Write the input and read the output together - O(i + o + w)
output, error = process.communicate(input="hello\n")
print(repr(output))  # 'hello\n'
print(process.returncode)  # 0 - set by communicate()
```

`communicate()` drains stdout and stderr at the same time. Reading one stream to the end yourself, `process.stdout.read()`, blocks for good once the child has filled the other pipe and is waiting for someone to empty it.

## Timeouts

```python
import subprocess

# The child is killed and collected before the exception reaches you
try:
    subprocess.run(["sleep", "10"], timeout=0.2)
except subprocess.TimeoutExpired as error:
    print(error.cmd)  # ['sleep', '10']

# communicate() keeps the output so far; the child keeps running
process = subprocess.Popen(["sleep", "10"], stdout=subprocess.PIPE)
try:
    process.communicate(timeout=0.2)
except subprocess.TimeoutExpired:
    process.kill()  # O(1) - sends SIGKILL and returns
    output, _ = process.communicate()  # O(o + w) - collects the exit
print(process.returncode)  # -9
```

## Pipe Chaining

```python
import subprocess

# Each stage is its own process; the pipe between them is the kernel's
producer = subprocess.Popen(["echo", "alpha\nbeta\ngamma"], stdout=subprocess.PIPE)
consumer = subprocess.Popen(
    ["grep", "beta"],
    stdin=producer.stdout,
    stdout=subprocess.PIPE,
    text=True,
)
producer.stdout.close()  # let the producer see a broken pipe if grep exits

output, _ = consumer.communicate()  # O(o + w) - o = grep's output
producer.wait()  # O(w)
print(repr(output))  # 'beta\n'
```

## Version Notes

- **Python 3.10+**: `Popen()` takes `pipesize`
- **Python 3.11+**: `Popen()` takes `process_group`; `getoutput()` and `getstatusoutput()` take `encoding` and `errors`
- **Python 3.12+**, and 3.10.11 and 3.11.3: on Windows, `shell=True` finds `cmd.exe` through `COMSPEC` and `SystemRoot`, no longer through the current directory or `PATH`
- **Python 3.13+**: `STARTF_FORCEONFEEDBACK` and `STARTF_FORCEOFFFEEDBACK` added on Windows

## Best Practices

✅ **Do**:

- Use `run()` for simple commands
- Use `capture_output=True` or `communicate()` when reading both streams
- Give a full path to a program you start many times
- Check return codes, or pass `check=True`
- Pass a `timeout`

❌ **Avoid**:

- Shell injection (use a list, not `shell=True` with a formatted string)
- `stdout=PIPE` with `call()` or `check_call()`, or with a child that writes more than a pipe holds and nobody reading
- Dropping a `Popen` without waiting for it
- Ignoring return codes

## Related Documentation

- [os Module](os.md) - `fork()`, `exec*()` and `waitpid()`, the calls underneath
- [asyncio Module](asyncio.md) - `create_subprocess_exec()` for the event loop
- [shlex Module](shlex.md) - Splitting and quoting command lines
- [multiprocessing Module](multiprocessing.md) - Python code in child processes
- [signal Module](signal.md) - What `terminate()` and `kill()` send
