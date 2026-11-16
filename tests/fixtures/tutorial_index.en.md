---
title: "L9 - Fixtures"
weight: 99
---

# Tutorial 9 - Fixtures

{{< hint info >}}
Read the man pages before the class.
{{< /hint >}}

## Reading a directory

Use `opendir` and `readdir` (`man 3p fdopendir`) to walk a directory.

{{< includecode "demo.c" >}}

{{< answer >}}
Because the stream must be closed with `closedir`.
{{</ answer >}}

{{< details "Answer" >}} A directory entry is a `dirent` structure. {{< /details >}}

## Links

- [Task 1]({{< ref "/sop1/lab/l9/example1" >}})
- [demo]({{< resource demo.c >}})
