# Summary: SOP1 lab 2 - Processes, Signals and Descriptors

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP1 lab 2 - Processes, Signals and Descriptors

Source: https://sop.mini.pw.edu.pl/en/sop1/lab/l2/

- Lab id: `sop1/l2`
- Tutorial sections: 31
- Tasks: 3
- Source files: 6

## Topics

`fork`, `getpid`, `getppid`, `sleep`, `ERR`, `kill`, `PID`, `time`, `wait`, `waitpid`, `NULL`, `WCONTINUED`, `WNOHANG`, `WUNTRACED`, `ECHILD`, `SIGTERM`, `SIGKILL`, `SIGUSR1`, `signal`, `sigaction`, `SIG_IGN`, `SIG_DFL`, `SA_SIGINFO`, `SIGUSR2`, `nanosleep`, `alarm`, `memset`, `SIGCHLD`, `SIGALRM`, `create_children`, `sigsuspend`, `sigemptyset`, `sigaddset`, `sigprocmask`, `SIG_BLOCK`, `SIG_SETMASK`, `SIG_UNBLOCK`, `pthread_sigmask`, `SIGINT`, `SIGUSER2`, `urandom`, `open`, `mknod`, `fprintf`, `close`, `EINTR`, `TEMP_FAILURE_RETRY`, `read`, `write`, `SA_RESTART`

## Tutorial outline

- **Tutorial 2 - Processes, Signals and Descriptors** - # Tutorial 2 - Processes, Signals and Descriptors > This tutorial contains the explanations for the used functions and their parameters. > It is still only a surface-level tutorial and it is **vital that you read the man pages** to familiarize yourself and understand all of the details.
  - **Process Management** - ## Process Management
    - **Creating Processes** - ### Creating Processes A child process is created using the `fork` command. Let’s take a look at the definition of this function: ``` pid_t fork(void) ``` As you can see, it returns an object of type `pid_t`, which is a signed integer type. In the parent process, the function returns the identifier 
    - **Process Identification** - ### Process Identification Each process has a unique identifier of type `pid_t`. To obtain information about the process identifier, we use the `getpid()` function, and to find out the identifier of the parent process, we use the `getppid()` function. Their definitions are as follows: ``` pid_t getp
    - **Exercise** - ### Exercise Write a program that creates 'n' sub-processes (n is 1st program parameter), each of those processes waits for random [5-10]s time then prints its PID and terminates. Parent process prints the number of alive child processes every 3s. For now, do not worry about waiting for child proces
    - **Solution** - ### Solution <em>solution <b>prog13a.c</b>:</em> ```c #include <errno.h> #include <stdio.h> #include <stdlib.h> #include <string.h> #include <sys/time.h> #include <sys/wait.h> #include <time.h> #include <unistd.h> #define ERR(source) \ (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source),
    - **Notes and questions** - ### Notes and questions - Make sure you know how the process group is created by shell, what processes belong to it? - Please note that macro `ERR` was extended with `kill(0, SIGKILL)`, it is meant to terminate the whole program (all other processes) in case of error. - Provide zero as pid argument 
    - **Waiting for Child Processes** - ### Waiting for Child Processes After completing the execution of all its instructions, a child process enters the **zombie** state (its identifier still remains in the process table) and stays in this state until the parent process retrieves information about its status (`Status Information` from `
    - **Exercise** - ### Exercise Extend the program from the previous exercise to correctly wait for child processes. New man pages - man 3p wait - man 3p waitpid - <a href="https://www.gnu.org/software/libc/manual/html_node/Job-Control.html">Job Control</a>
    - **Solution** - ### Solution <em>solution <b>prog13b.c</b>:</em> ```c #include <errno.h> #include <stdio.h> #include <stdlib.h> #include <string.h> #include <sys/time.h> #include <sys/wait.h> #include <time.h> #include <unistd.h> #define ERR(source) \ (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source),
    - **Notes and questions** - ### Notes and questions - It is worth knowing that `waitpid` can tell us about temporary lack of terminated children (returns zero) and about permanent lack of them (error `ECHILD`). The second case is not a critical error, your code should expect it. - Why `waitpid` is in a loop? **Answer:** we do 
  - **Signals** - ## Signals Signals are an asynchronous event-handling mechanism used in Unix-like operating systems. They allow notifying processes about the occurrence of specific system events, exceptions, or requests to control execution.
    - **Sending signals** - ### Sending signals Signals are sent using the `kill` function: ``` c #include <signal.h> int kill(pid_t pid, int sig); ``` The `pid` argument specifies which process or group of processes the signal is directed to: - `pid > 0` - the signal is sent to the process with PID equal to `pid` - `pid = 0` 
    - **Signal handling** - ### Signal handling Each signal has a default behavior assigned to it. You can check the list of signals and their default behavior using: ``` man 7 signal ``` The way a signal is handled can be checked or changed using: ``` c #include <signal.h> int sigaction(int sig, const struct sigaction *restri
    - **Task** - ### Task The program takes 4 positional parameters (`n`, `k`, `p`, and `r`). It creates `n` child processes. The parent alternately sends `SIGUSR1` and `SIGUSR2` to all children in a loop, waiting `k` and `p` seconds respectively. It terminates when all child processes end. Each child process random
    - **Solution** - ### Solution <em>solution <b>prog14.c</b>:</em> ```c #include <errno.h> #include <stdio.h> #include <stdlib.h> #include <string.h> #include <sys/wait.h> #include <time.h> #include <unistd.h> #define ERR(source) \ (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source), kill(0, SIGKILL), exit
  - **Waiting for a Signal** - ## Waiting for a Signal Often, when writing programs, we encounter a situation where a process, before performing its work, must be informed that another process has completed its task. As you might guess, this problem can be easily solved using __signals__. Inspired by the previous task, we could w
    - **Managing the Signal Mask** - ### Managing the Signal Mask A set of signals is called a signal mask. We will store the signal mask as an object of type `sigset_t`. The standard does not specify how this type should be implemented; it can be either an `int` or a structure. To modify the signal mask, we use the functions `sigempty
    - **Changing the Signal Mask** - ### Changing the Signal Mask Once we have defined a new signal mask, we want it to affect the operation of our process. For this purpose, we use the `sigprocmask` function, which determines how the signal mask we defined should affect the current signal mask of the process. Let’s look at its definit
    - **Exercise** - ### Exercise Write a program that starts one child process, which sends every "m" (parameter) microseconds a `SIGUSR1` signal to the parent. Every n-th signal is changed to `SIGUSR2`. Parent anticipates `SIGUSR2` and counts the amount of signals received. Child process also counts the amount of `SIG
    - **Solution** - ### Solution <em>solution part <b>prog15.c</b>:</em> ```c #include <errno.h> #include <stdio.h> #include <stdlib.h> #include <string.h> #include <sys/wait.h> #include <time.h> #include <unistd.h> #define ERR(source) \ (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source), kill(0, SIGKILL),
    - **Notes and questions** - ### Notes and questions - Try it with various parameters. The shorter microsecond brake and more frequent `SIGUSER2` the faster growing gap between counters should be observable. In a moment the difference in numbers will be explained. If you do not observe the shift between counters let the program
  - **Low-level file operations and signals** - ## Low-level file operations and signals In this part of the tutorial, we will begin by showing what problems can arise during file operations while signals are being handled simultaneously, and then we will demonstrate how to deal with them.
    - **Task** - ### Task Modify the previous program so that the parent process receives `SIGUSR1` signals sent at a specified interval (parameter `1`) and counts them. Additionally, the main process creates a file with a name given as parameter 4, containing a specified number of blocks of a given size (parameters
    - **Incorrect solution** - ### Incorrect solution *file **prog16a.c**:* ```c #include <errno.h> #include <fcntl.h> #include <stdio.h> #include <stdlib.h> #include <string.h> #include <sys/stat.h> #include <sys/wait.h> #include <time.h> #include <unistd.h> #define ERR(source) \ (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), 
    - **Problems** - ### Problems After running the program with parameters `1 20 40 out.txt`, you should observe the following problems: - Copying shorter blocks than expected. On my laptop, I never exceed 33,554,431 bytes even though it should be 40 MB, and shorter blocks sometimes occur as well. The reason is that th
    - **Notes and questions** - ### Notes and questions Why does the parent process send `SIGUSR1` to the entire group at the end? **Answer:** To terminate the child process. How can the child process terminate upon receiving `SIGUSR1` if it inherited the handler for this signal? **Answer:** Immediately after starting, the child r
    - **Solving the problems** - ### Solving the problems During I/O operations, functions can be interrupted by the signal handler. In such a case, the functions return `-1` to indicate an error and set `errno` to `EINTR`. The POSIX standard states that in such a case, the function is interrupted before it achieves anything. There
    - **Notes and questions** - ### Notes and questions What other interruption in the program can the signal handler cause? **Answer:** It can interrupt I/O operations or sleeping; these are not reported through `EINTR`. In both cases, handling the event is not trivial. How do we know which functions can be interrupted before the
  - **Example tasks** - ## Example tasks Do the example tasks. During the laboratory you will have more time and a starting code. If you do following tasks in the allotted time, it means that you are well-prepared. - [Task 1](https://sop.mini.pw.edu.pl/en/sop1/lab/l2/example1/) ~75 minutes - [Task 2](https://sop.mini.pw.ed
  - **Source codes presented in this tutorial** - ## Source codes presented in this tutorial - [prog13a.c](prog13a.c) - [prog13b.c](prog13b.c) - [prog14.c](prog14.c) - [prog15.c](prog15.c) - [prog16a.c](prog16a.c) - [prog16b.c](prog16b.c)

## Tasks

- **example1: Graded task on Processes, Signals and Descriptors** - 5 stages
  1. Program creates “n” children, each child process chooses random “s” and prints it on the screen. Parent can exit prior to its children
  2. Child process sends 30 times SIGUSR1 to its parent in a loop with “s” delay, print one “\*” for each signal sent (4p)
  3. Parent process counts the SIGUSER1 and prints counter every time it receives the signal. At this stage it must be terminated with C-c. (4p)
  4. When counter in parent process reaches 100 terminate the child processes and exit, child process are modified to send SIGUSR1 until they receive SIGUSR2 (3p)
  5. Wait for child processes at the end of parent and eliminate possible zombies during the operation (SIGCHLD)(3p)
- **example2: Graded task no. 2 on Processes, Signals and Descriptors** - 4 stages
  1. The teacher process starts students processes, children print onto stdout their PIDs and probability value, then exit. The parent awaits the children. (4p)
  2. Student processes do the task according to the description and send signals to the teacher (they do not wait for a response, just continue the work). (5p)
  3. The teacher process receives the signals from students and responds to them. The student waits for the task part confirmation. (4p)
  4. The teacher collects information about issues and prints them. (3p)
- **example3: Graded task no. 2 on Processes, Signals and Descriptors** - 4 stages
  1. The parent creates children. The children print out their PID and indices and terminate. The parent awaits termination of all children and exits. **(3pt)**
  2. The parent instructs the first child to do work by sending SIGUSR1 to it. The child performs the work in a loop. **(5pt)**
  3. Handling of SIGUSR1 by the parent, handling of SIGUSR2 by the children. **(4pt)**
  4. Handling of SIGINT. Saving the counters to the file by children. **(4pt)**

## Source files

- `src/prog13a.c` (c)
- `src/prog13b.c` (c)
- `src/prog14.c` (c)
- `src/prog15.c` (c)
- `src/prog16a.c` (c)
- `src/prog16b.c` (c)
