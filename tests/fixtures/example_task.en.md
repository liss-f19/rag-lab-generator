---
title: "Example task 1 on fixtures"
bookHidden: true
---

## Description

Write a program that opens a directory with `opendir` and prints its entries.

```c
/* ## not a heading */
DIR *dir = opendir(".");
```

## Stages

1. Open the directory and print the entries. *To show:* run without parameters.
2. Print the size of every entry using `stat`.
3. Move the output to `out.txt`.

## Starting code

- [fixture.zip](/files/fixture.zip)
