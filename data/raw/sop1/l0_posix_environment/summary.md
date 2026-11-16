# Summary: SOP1 lab 0 - POSIX program execution environment

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP1 lab 0 - POSIX program execution environment

Source: https://sop.mini.pw.edu.pl/en/sop1/lab/l0/

- Lab id: `sop1/l0`
- Tutorial sections: 13
- Tasks: 0
- Source files: 9

## Topics

`SIG_BLOCK`, `stdin`, `printf`, `EXIT_SUCCESS`, `EXIT_FAILURE`, `fscanf`, `perror`, `fprintf`, `scanf`, `tcsetattr`, `fgets`, `xargs`, `exit`, `atoi`, `strtol`, `environ`, `getenv`, `putenv`, `setenv`, `system`, `EINVAL`, `usage`

## Tutorial outline

- **Introduction Lab for OPS1** - # Introduction Lab for OPS1 > This laboratory does not require any preparation, its aim is to explain all the rules and answer all the question about graded labs and the classes schedule. Please carefully read everything about [GIT](https://sop.mini.pw.edu.pl/en/info/git/), [syllabus](https://sop.mi
  - **Environment preparation** - ## Environment preparation Unlike the previous classes, we do not require any particular IDE. However, a good editor should: - Show live compilation errors (which allows us to learn about them and find relevant code quicker). - Autocomplete function names (helpful while entering longer names). - Giv
  - **Tasks preparing to laboratory** - ## Tasks preparing to laboratory > Introduction notes: > > - This tutorial is fairly easy and rather long, next ones will be harder and shorter > - Quick look at this material will not suffice, you should compile and run all the programs, check how they work, read > additional materials like man pag
  - **Task 1 - stdout** - ## Task 1 - stdout Goal: Write and compile (using make program) the simplest program to write on the standard output. What you need to know: - man 3p stdin - man 3p printf - man stdlib.h - man make - Tutorial on gcc and make, <a href="tutorial.gcc_make.txt">link</a> I'd like to discourage you from m
  - **Task 2 - stdin, stderr** - ## Task 2 - stdin, stderr Goal: Extend prog1 to print out the welcome message for the name from the standard input. Names above 20 chars should generate error (message and immediate exit). What you need to know: - man 3p fscanf - man 3p perror - man 3p fprintf For convenience lets add macro: ```c #d
  - **Task 3 - stdin cd..** - ## Task 3 - stdin cd.. Goal: Extend prog2.c to print welcome message for each name given from the standard input. Program should consume lines of text (up to 20 chars) and print on the standard output. The operation repeats until the end of stream (EOF) condition (`C-s`). Lines above 20 chars should
  - **Task 4 - program parameters 1** - ## Task 4 - program parameters 1 Goal: Write code to display all the program execution parameters. What you need to know: - man 1 xargs <em>code for <b>prog4.c</b></em> ```c #include <stdio.h> #include <stdlib.h> #include <string.h> #define MAX_LINE 20 int main(int argc, char **argv) { int i; for (i
  - **Task 5 - program parameters 2** - ## Task 5 - program parameters 2 Goal: Write a program that accepts 2 arguments: name and counter n &gt; 0, more than two parameters or invalid counter should stop the program. For correct parameters print "Hello NAME" n-times What you need to know: - man 3p exit - man 3p atoi - man 3p strtol <em>Ad
  - **Task 6 - environment variables 1** - ## Task 6 - environment variables 1 Goal: List all the environmental variables of the process What you need to know: - man 3p environ - man 7 environ <em>code for <b>prog6.c</b> file:</em> ```c #include <stdio.h> #include <stdlib.h> #include <string.h> #include <unistd.h> extern char **environ; int 
  - **Task 7 - environmental variables 2** - ## Task 7 - environmental variables 2 Goal: Enhance prog3.c to multiply each welcome line of text as many times as environmental variable TIMES says. At the end of the program set RESULT environmental variable to "Done" value. What you need to know: - man 3p getenv - man 3p putenv - man 3p setenv - 
  - **Task 8 - error handling** - ## Task 8 - error handling Goal: Modify program prog6.c to add append new environmental variables passed by user and then list all them all. What you need to know: - man 3p errno <em>code for <b>prog8.c</b> file:</em> ```c #include <errno.h> #include <stdio.h> #include <stdlib.h> #include <string.h>
  - **The task for IDE testing** - ## The task for IDE testing Goal: Write a trivial program "hello world", compile and run it. *What student has to know:* - know one of available (in our labs) programmers environment for Linux - know how to do basic compilation with gcc - know how to use a command line interface - fundamental know h
  - **Source codes presented in this tutorial** - ## Source codes presented in this tutorial - [prog1.c](prog1.c) - [prog2.c](prog2.c) - [prog3.c](prog3.c) - [prog4.c](prog4.c) - [prog5.c](prog5.c) - [prog6.c](prog6.c) - [prog7.c](prog7.c) - [prog8.c](prog8.c)

## Source files

- `src/prog1.c` (c)
- `src/prog2.c` (c)
- `src/prog3.c` (c)
- `src/prog4.c` (c)
- `src/prog5.c` (c)
- `src/prog6.c` (c)
- `src/prog7.c` (c)
- `src/prog8.c` (c)
- `src/tutorial.gcc_make.txt` (text)
