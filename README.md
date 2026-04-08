# libimportx-python
Python implementation of libimportx
# Usage
this is a very simple library. there are many functions and classes but you are
supposed to use these two: `importx` and `exportx`. everything else is used
under the hood to make it seamless.

## `exportx`
Call this function AFTER all your functions are defined but BEFORE the logic
that you want to run when the function is not `importx`'ed. This function will
allow the file to be `importx`'ed. If the file isnt being importx'ed the
function will return `False` and execution continues as normal. But if it is,
the function blocks and does not return (it exits when the thing importing this
exits or throws an error).

## `importx`

Use this function to import a file that calls `exportx`. It takes in the
filepath as an argument. To run the file, it tries these in order:
1) If there is an optional `cmd` argument, it uses that, replacing `$IN` with
the path to the file and `$OUT` with the path to a temporary file.
2) It checks the `LIBIMPORTX_DEFAULT_CMD_<extension>` (uppercase) env variable
for a command replacing `$IN` `$OUT`.
3) If the first line of the file starts with `#!` or `//!`, it uses the rest of
the line as the command and appends the filename as an argument (without
replacing `$IN` or `$OUT`).
4) If the first line of the file starts with `##!` or `///!`, it uses the rest
of the line as a command and replaces `$IN` `$OUT`
5) It checks the file extension and looks for a default command.
