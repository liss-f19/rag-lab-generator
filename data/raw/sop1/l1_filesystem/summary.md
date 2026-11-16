# Summary: SOP1 lab 1 - Filesystem

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP1 lab 1 - Filesystem

Source: https://sop.mini.pw.edu.pl/en/sop1/lab/l1/

- Lab id: `sop1/l1`
- Tutorial sections: 28
- Tasks: 3
- Source files: 6

## Topics

`opendir`, `readdir`, `fdopendir`, `DIR`, `dirent`, `inode`, `stat`, `lstat`, `fstatat`, `S_ISREG`, `S_ISDIR`, `S_ISLNK`, `closedir`, `NULL`, `ERR`, `scan_dir`, `getcwd`, `chdir`, `printf`, `ftw`, `nftw`, `FTW_D`, `FTW_F`, `FTW_SL`, `FTW_DNR`, `FTW_CHDIR`, `FTW_DEPTH`, `FTW_PHYS`, `walk`, `fopen`, `fseek`, `fprintf`, `fread`, `fclose`, `FILE`, `unlink`, `rand`, `umask`, `open`, `strtol`, `srand`, `read`, `write`, `close`, `mknod`, `TEMP_FAILURE_RETRY`, `GNU_SOURCE`, `bulk_read`, `bulk_write`, `writev`, `readv`

## Tutorial outline

- **Tutorial 1 - Filesystem** - # Tutorial 1 - Filesystem > This tutorial contains the explanations for the used functions and their parameters. > It is still only a surface-level tutorial and it is **vital that you read the man pages** to familiarize yourself and understand all of the details.
  - **Browsing a directory** - ## Browsing a directory Browsing a directory makes us possible to know names and attributes of the files which that directory contains. This task is accomplished e.g. by the terminal's command `ls -l`. However, in order to access this information from the C language, it is needed to 'open' the direc
    - **Technical information** - ### Technical information In order to browse the entire directory, the `readdir` function should be called repeatedly until it returns `NULL`. If an error occurs, both `opendir` and `readdir` return `NULL`. An important conclusion follows from this for the `readdir` function: before calling it, the 
    - **Exercise** - ### Exercise Write a program counting objects (files, links, folders and others) in current working directory.
    - **Solution** - ### Solution New man pages: ``` man 3p fdopendir (only opendir) man 3p closedir man 3p readdir man 0p dirent.h man 3p fstatat (only stat and lstat) man sys_stat.h man 7 inode (first half of the "The file type and mode" section) ``` solution `l1-1.c`: ```c #include <dirent.h> #include <errno.h> #incl
    - **Notes and questions** - ### Notes and questions - Run this program in the folder with some files but without sub-folders, it may be the folder you are working on this tutorial in. Is the folder count zero? Explain it. **Answer:** No, each folder has two special *hard-linked* folders -- `.` link to the folder itself and `..
  - **Working directory** - ## Working directory The program from the previous excercise only allowed to scan the contents of the directory, which it was run in. It would be much better to choose the directory to be scanned. As we can see, that it would be sufficient to replace the `opendir` argument to the path given e.g. in 
    - **Excercise** - ### Excercise Use function from `l1-1.c` to write a program that will count objects in all the folders passed to the program as positional parameters.
    - **Solution** - ### Solution New man pages: ``` man 3p getcwd man 3p chdir ``` solution `l1-2.c`: ```c #include <dirent.h> #include <errno.h> #include <stdio.h> #include <stdlib.h> #include <sys/stat.h> #include <unistd.h> #define MAX_PATH 101 #define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__
    - **Notes and questions** - ### Notes and questions - Check how this program deals with: - non existing folders, - no access folders, - relative paths and absolute paths as parameters. - Why does this program store the initial working folder? **Answer:** This is the solution to the case when the user specifies several relative
  - **Browsing directories and subdirectories (recursive)** - ## Browsing directories and subdirectories (recursive) If it were necessary to visit not only the working directory, but the entire directory subtree, the solution using `opendir` function would be problematic. Instead of this, we can use `ftw` and `nftw` functions, which are present in `<ftw.h>` he
    - **Excercise** - ### Excercise Write a program that counts all occurrences of the files, folders, symbolic links and other objects in a subtrees rooted at locations indicated by parameters.
    - **Solution** - ### Solution New man pages: ``` man 3p ftw man 3p nftw ``` solution `l1-3.c`: ```c #define _XOPEN_SOURCE 500 #include <dirent.h> #include <errno.h> #include <ftw.h> #include <stdio.h> #include <stdlib.h> #include <sys/stat.h> #include <unistd.h> #define MAXFD 20 #define ERR(source) (perror(source), 
    - **Notes and questions** - ### Notes and questions - If you do not understand the definition of `nftw` or the use of `walk` in the solution, make sure you know how to declare and use pointers to functions in C. - Test how this program reacts on not available or non-existing folders. - Why `FTW_PHYS` flag is applied? **Answer:
  - **File Operations** - ## File Operations A large portion of programs interact with files on the disk. The simplest way to achieve this is: 1. Opening (or creating) a file using `fopen` (`man 3p fopen`), 2. Setting the file cursor with `fseek` (`man 3p fseek`), 3. Writing data with `fprintf`, `fputc`, `fputs`, `fwrite`, o
    - **Task** - ### Task Write a program that creates a new file with a name specified by the parameter (-n NAME), permissions (-p OCTAL), and size (-s SIZE). The file’s content should be about 10% random characters [A-Z], with the rest filled with zeros (null characters with code 0, not '0'). If the specified file
    - **Solution Outline** - ### Solution Outline What the student needs to know: - man 3p fopen - man 3p fclose - man 3p fseek - man 3p rand - man 3p unlink - man 3p umask glibc documentation on umask <a href="http://www.gnu.org/software/libc/manual/html_node/Setting-Permissions.html">link</a> <em>code for file <b>prog12.c</b>
    - **Notes and questions** - ### Notes and questions - What bitmask is created by the expression `~perms&0777`? **Answer:** The inverse of permissions specified by the -p parameter, truncated to 9 bits. If unclear, review bitwise operations in C. - How does character randomization work? **Answer:** Sequential alphabet character
  - **Buffering of Standard Output** - ## Buffering of Standard Output
    - **Experiment** - ### Experiment **Code for file** `prog13.c` ```c #include <stdio.h> #include <stdlib.h> #include <unistd.h> int main() { for (int i = 0; i < 15; ++i) { // Output the iteration number and then sleep 1 second. printf("%d\n", i); sleep(1); } return EXIT_SUCCESS; } ``` - Try running this (very simple!) 
  - **Low-Level File Operations** - ## Low-Level File Operations You can also use low-level functions to read and write files-functions provided directly by the operating system rather than by the C standard library. With these functions, you can, for instance, send packets over a network, which we’ll cover in the next semester. Inste
    - **Task** - ### Task Write a simple program that copies files. It should accept two paths as arguments and copy the file from the first path to the second. This time, use low-level functions.
    - **Task Solution** - ### Task Solution What the student needs to know: - `man 3p open` - `man 3p close` - `man 3p read` - `man 3p write` - `man 3p mknod` (only constants describing permissions for `open`) - Description of the macro `TEMP_FAILURE_RETRY` [here](http://www.gnu.org/software/libc/manual/html_node/Interrupted
    - **Notes and Questions** - ### Notes and Questions To use the `TEMP_FAILURE_RETRY` macro, you must first define `GNU_SOURCE` and then include the header file `unistd.h`. You don’t need to fully understand how this macro works yet; it will be more important in the next lab when we cover signals. - Why does the program above us
  - **Vectorized File Operations** - ## Vectorized File Operations The `writev` function (see `man 3p writev`) provides a convenient solution when the data we want to write isn’t in a single continuous memory fragment. It allows us to gather data from multiple locations and write it to a file with a single function call. It’s defined i
    - **Useful pages** - ### Useful pages - man 3p writev - man 3p readv - man 0p sys_uio.h
  - **Example tasks** - ## Example tasks Do the example tasks. During the laboratory you will have more time and the starting code. However, if you finish the following tasks in the recommended time, you will know you're well prepared for the laboratory. - [Task 1](https://sop.mini.pw.edu.pl/en/sop1/lab/l1/example1/) ~75 m
  - **Source codes presented in this tutorial** - ## Source codes presented in this tutorial - [l1-1.c](l1-1.c) - [l1-2.c](l1-2.c) - [l1-3.c](l1-3.c) - [prog12.c](prog12.c) - [prog13.c](prog13.c) - [prog14.c](prog14.c)

## Tasks

- **example1: Example task 1 on POSIX program environment** - 6 stages
  1. Program lists the names of objects in the working folder. *To show:* run the program without params
  2. Program lists the sizes (without names) of objects in the working folder, counts the sum of sizes and prints it on the screen. *To show:* run the program without params
  3. Extend the code to accept folders as parameters (sizes are ignored) and repeat the printout for every folder. *To show:* run the program with params: `/etc 1000 /run 200`
  4. Program prints only the names of folders if the content size is above the limit. *To show:* run the program with params: `/etc 1000 /run 200`, adjust the sizes so one folder will be printed and other not
  5. Implement an alternative version of stage 4. using low-level FS functions, i.e. `open`, `close` and `read`.
  6. Move output to the file out.txt, add message on access problems. To show: run the program with params as in the example below the task.
- **example2: Example task 2 on POSIX program environment** - 4 stages
  1. The program lists the names of the files of each provided directory on stdout, not skipping anything yet and ignoring other arguments. Run with `-d 1` flag
  2. Program lists files with their sizes and option `-e` works
  3. Option `-d` works
  4. Option `-o` works
- **example3: Example task 3 on POSIX program environment** - 4 stages
  1. Implementation of environment creation
  2. Implementation of package installation and handling described errors
  3. Ability to use the `-v` option multiple times
  4. Implementation of package removal

## Source files

- `src/l1-1.c` (c)
- `src/l1-2.c` (c)
- `src/l1-3.c` (c)
- `src/prog12.c` (c)
- `src/prog13.c` (c)
- `src/prog14.c` (c)
