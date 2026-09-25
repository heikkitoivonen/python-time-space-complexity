# cmd Module Complexity

The `cmd` module turns a class into a line-oriented command interpreter. `Cmd.cmdloop()` reads a
line, splits the command name off the front, and calls the method named `do_<command>` with the
rest. The unit of work is one input line.

`k` is the characters in the command line being run, `a` is the names `dir()` reports for the
interpreter's class (every `do_`, `help_` and `complete_` method, plus those inherited from `Cmd`
and `object`), `n` is the strings `columnize()` lays out, `q` is the lines waiting in `cmdqueue`,
and `t` is the characters in the docstring `help` shows for a topic. Every bound is what `cmd` adds
around a handler: the `do_`, `help_` and `complete_` methods' own work is not included. Names and
the strings `columnize()` lays out are counted, not measured: their lengths are treated as short
and not priced. `identchars` is treated as a fixed-size string, and attribute lookup as O(1).

## Complexity Reference

### Cmd

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cmd.Cmd(completekey='tab', stdin=None, stdout=None)` | O(1) | O(1) | Stores the streams and an empty `cmdqueue`; `stdin` is read only when `use_rawinput` is false |
| `Cmd.cmdloop(intro=None)` | O(k) per line | O(k) | Runs until `postcmd()` returns a true value, which by default is whatever the handler returned; end of input arrives as the line `'EOF'`. A line taken from `cmdqueue` adds O(q) |
| `Cmd.onecmd(line)` | O(k) | O(k) | One `parseline()` and one attribute lookup for `do_<command>`, however many commands the class has |
| `Cmd.parseline(line)` | O(k) | O(k) | Returns `(command, args, line)`; a leading `?` becomes `help`, and `!` becomes `shell` when `do_shell` exists |
| `Cmd.emptyline()` | O(k) | O(k) | Runs `lastcmd` again through `onecmd()`, so an empty line costs what the last command cost; O(1) when there is none |
| `Cmd.default(line)` | O(k) | O(k) | Writes `*** Unknown syntax:` and the line |
| `Cmd.precmd(line)`, `Cmd.postcmd(stop, line)` | O(1) | O(1) | Called for every line; the defaults return `line` and `stop` unchanged |
| `Cmd.preloop()`, `Cmd.postloop()` | O(1) | O(1) | Called once as `cmdloop()` starts and once as it returns; empty by default |
| `Cmd.cmdqueue` | O(q) per line taken | O(q) | A list the loop reads with `pop(0)` before asking for input, so replaying q queued lines is O(q²) in all |

### Help and completion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Cmd.do_help(arg)` for one topic | O(k + t) | O(k + t) | Calls `help_<topic>()` when it exists, otherwise prints the docstring of `do_<topic>` |
| `Cmd.do_help('')`, `help` alone | O(a log a + n²) | O(a) | One `get_names()`, then one `print_topics()` each for documented commands, help topics and undocumented commands |
| `Cmd.print_topics(header, cmds, cmdlen, maxcol)` | O(n²) | O(n) | A header, a `ruler` line under it when `ruler` is set, then `columnize(cmds, maxcol - 1)`; prints nothing for an empty list |
| `Cmd.columnize(list, displaywidth=80)` | O(n²) | O(n) | Tries each row count from one upward until the columns fit, measuring the strings again each time; a list that fits on one line is O(n) |
| `Cmd.get_names()` | O(a log a) | O(a) | The class's `dir()`, which is sorted; every `help` listing and every command-name completion calls it |
| `Cmd.complete(text, state)` | O(k + a log a) at state 0, O(1) after | O(k + a) | The readline completer: state 0 builds the whole match list and later states index it. For an argument, state 0 costs O(k) plus the `complete_<command>` method |
| `Cmd.completenames(text, *ignored)` | O(a log a) | O(a) | Command names starting with `text` |
| `Cmd.complete_help(*args)` | O(a log a) | O(a) | Command names and `help_` topics starting with the text |
| `Cmd.completedefault(*ignored)` | O(1) | O(1) | Returns an empty list; override it to complete the arguments of commands that have no `complete_` method |

### Attributes and constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Cmd.prompt`, `Cmd.intro`, `Cmd.ruler`, `Cmd.doc_leader`, `Cmd.doc_header`, `Cmd.misc_header`, `Cmd.undoc_header`, `Cmd.nohelp` | O(1) | O(1) | Text read each time it is printed; set it on the subclass or on the instance |
| `Cmd.identchars` | O(1) | O(1) | The characters a command name may contain; parsing stops at the first character outside it |
| `Cmd.lastcmd` | O(1) | O(1) | The line `emptyline()` repeats, as `parseline()` returned it; `EOF` resets it to `''` |
| `Cmd.use_rawinput` | O(1) | O(1) | True: `input()`, with readline editing and completion where `readline` is available. False: `stdin.readline()`, and only then is the `stdin` argument used |
| `cmd.PROMPT`, `cmd.IDENTCHARS` | O(1) | O(1) | The defaults for `prompt` and `identchars` |

## Running an Interpreter

### Reading From a Stream

With `use_rawinput` false the loop writes the prompt to `stdout` and reads `stdin` a line at a
time, so a session costs O(k) per line on top of its handlers, and a script of any length is
never held whole. The line `'EOF'` arrives once the stream is exhausted.

```python
import cmd
import io

class Shell(cmd.Cmd):
    prompt = '> '
    use_rawinput = False  # read the stdin argument, not the terminal

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.greeted = []

    def do_greet(self, arg):
        """Greet someone: greet NAME"""
        self.greeted.append(arg)

    def do_EOF(self, arg):
        return True  # stop the loop at end of input

output = io.StringIO()
shell = Shell(stdin=io.StringIO("greet Ada\ngreet  Alan \n"), stdout=output)
shell.cmdloop()  # O(k) per line

assert shell.greeted == ['Ada', 'Alan']
assert output.getvalue() == '> > > '  # one prompt per line read, including the end
```

### End of Input

A class without `do_EOF` sends `'EOF'` to `default()`, which prints an error and returns nothing,
so on a file or pipe the loop reads again, finds it still exhausted, and never stops. Define `do_EOF` and
return a true value from it.

```python
import cmd
import io

output = io.StringIO()
shell = cmd.Cmd(stdout=output)

assert shell.onecmd('EOF') is None  # nothing tells the loop to stop
assert output.getvalue() == '*** Unknown syntax: EOF\n'

class Stoppable(cmd.Cmd):
    def do_EOF(self, arg):
        return True

assert Stoppable().onecmd('EOF') is True
```

## Parsing and Dispatch

`parseline()` strips the line and takes the longest prefix made of `identchars` as the command
name. `onecmd()` then looks up `do_<command>` as one attribute, so dispatch costs the same with
five commands or five thousand; only `help` and completion enumerate them.

```python
import cmd
import io

class Shell(cmd.Cmd):
    def do_add(self, arg):
        """Add integers: add 1 2 3"""
        self.total = sum(int(part) for part in arg.split())

    def do_shell(self, arg):
        self.ran = arg

shell = Shell(stdout=io.StringIO())

assert shell.parseline('  add 1 2 ') == ('add', '1 2', 'add 1 2')  # O(k)
assert shell.parseline('?add') == ('help', 'add', 'help add')
assert shell.parseline('!ls -l') == ('shell', 'ls -l', 'shell ls -l')
assert shell.parseline('add-1') == ('add', '-1', 'add-1')  # '-' is not in identchars

shell.onecmd('add 10 20')  # O(k) - one lookup for do_add
assert shell.total == 30

shell.onecmd('multiply 2 3')  # no do_multiply: default() reports it
assert shell.stdout.getvalue() == '*** Unknown syntax: multiply 2 3\n'
```

### Empty Lines Repeat the Last Command

An empty line calls `emptyline()`, which runs `lastcmd` again. That costs whatever the last
command cost and repeats its effects; override `emptyline()` to make an empty line do nothing.

```python
import cmd

class Counter(cmd.Cmd):
    count = 0

    def do_inc(self, arg):
        self.count += 1

class Quiet(Counter):
    def emptyline(self):
        pass  # O(1) - nothing is repeated

counter = Counter()
counter.onecmd('inc')
counter.onecmd('')  # runs 'inc' again
assert counter.count == 2
assert counter.lastcmd == 'inc'

quiet = Quiet()
quiet.onecmd('inc')
quiet.onecmd('')
assert quiet.count == 1
```

### Queued Lines

The loop takes lines from `cmdqueue` before it reads any input. The queue is a list consumed with
`pop(0)`, which shifts every remaining line, so a handful of queued commands is cheap and a
recorded script of q lines costs O(q²) to replay; stream a long script through `stdin` instead.

```python
import cmd
import io

class Shell(cmd.Cmd):
    use_rawinput = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seen = []

    def default(self, line):
        self.seen.append(line)

    def do_EOF(self, arg):
        return True

shell = Shell(stdin=io.StringIO("typed\n"), stdout=io.StringIO())
shell.cmdqueue.extend(['first', 'second'])  # O(1) amortized per line
shell.cmdloop()  # O(q) per queued line taken

assert shell.seen == ['first', 'second', 'typed']
assert shell.cmdqueue == []
```

## Help and Completion

### Listing Commands

`help` on its own is the one command that walks the class. It sorts every name `dir()` reports,
groups the `do_` and `help_` methods, and lays each group out in columns. `columnize()` tries one
row, then two, and so on, measuring the strings again for each attempt, so it is quadratic in the
strings once they wrap onto many rows. Help for one topic looks up at most two methods.

```python
import cmd
import io

class Shell(cmd.Cmd):
    ruler = '-'

    def do_add(self, arg):
        """Add integers."""

    def do_quit(self, arg):
        return True

    def help_syntax(self):
        self.stdout.write('Commands are words followed by arguments.\n')

output = io.StringIO()
shell = Shell(stdout=output)

shell.onecmd('help')  # O(a log a + n²)
listing = output.getvalue()
assert 'Documented commands (type help <topic>):\n' in listing
assert 'add  help\n' in listing  # do_help has a docstring too
assert 'Miscellaneous help topics:\n---' in listing
assert 'Undocumented commands:\n----------------------\nquit\n' in listing

output.seek(0)
output.truncate()
shell.onecmd('help add')  # O(k + t) - one docstring
assert output.getvalue() == 'Add integers.\n'

output.seek(0)
output.truncate()
shell.columnize(['one', 'two', 'three'], displaywidth=10)  # O(n²)
assert output.getvalue() == 'one  three\ntwo\n'
```

### Completing Command Names

When readline asks for completions, state 0 computes every match and later states read the stored
list. Completing a command name calls `get_names()`, so it costs O(k + a log a) per Tab press; an
argument goes to `complete_<command>()`, or to `completedefault()` when there is none.

```python
import cmd

class Shell(cmd.Cmd):
    def do_hello(self, arg):
        pass

    def do_help_me(self, arg):
        pass

    def help_hello(self):
        pass

    def help_history(self):
        pass

shell = Shell()

assert shell.completenames('hel') == ['hello', 'help', 'help_me']  # O(a log a)
assert sorted(shell.complete_help('h')) == ['hello', 'help', 'help_me', 'history']
assert shell.completedefault('x', 'unknown x', 8, 9) == []  # O(1)
```

## Common Patterns

### Testing a Shell Without a Terminal

`onecmd()` is the loop's per-line work without the input or the `precmd()` and `postcmd()` hooks,
so a shell can be driven and checked line by line with its output captured.

```python
import cmd
import io

class Store(cmd.Cmd):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data = {}

    def do_set(self, arg):
        key, value = arg.split(maxsplit=1)
        self.data[key] = value  # O(1) average

    def do_get(self, arg):
        self.stdout.write(f"{self.data.get(arg, '')}\n")

output = io.StringIO()
store = Store(stdout=output)

for line in ['set name Ada', 'set lang Python', 'get name']:
    store.onecmd(line)  # O(k) per line, plus the handler

assert store.data == {'name': 'Ada', 'lang': 'Python'}
assert output.getvalue() == 'Ada\n'
```

## Performance Best Practices

✅ **Do**:

- Stream a long script through `stdin` with `use_rawinput = False`: O(k) per line, with nothing
  held but the current line
- Define `do_EOF` and return a true value, so the loop stops at end of input
- Override `emptyline()` when repeating the last command is costly or unwanted
- Call `onecmd()` directly to test handlers; it is one line's work without the prompt or the
  `precmd()` and `postcmd()` hooks

❌ **Avoid**:

- Queuing a long script in `cmdqueue` - each line taken shifts the rest, O(q²) in all
- Passing `columnize()` thousands of strings - it is O(n²) once they wrap onto many rows
- Passing `stdin=` with `use_rawinput` left true - the loop reads the terminal and ignores it

## Version Notes

- **Python 3.13+**: `completekey='tab'` binds Tab when `readline` is backed by libedit; on
  earlier versions Tab inserts a tab character there instead of completing

## Related Modules

- **[readline](readline.md)** - the line editing, history and completion `cmdloop()` uses when
  `use_rawinput` is true
- **[shlex](shlex.md)** - splits a handler's argument string with shell-style quoting
- **[code](code.md)** - an interactive Python interpreter rather than a command language
