# Summary: SOP1 lab 3 - Threads, mutexes and signals

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP1 lab 3 - Threads, mutexes and signals

Source: https://sop.mini.pw.edu.pl/en/sop1/lab/l3/

- Lab id: `sop1/l3`
- Tutorial sections: 29
- Tasks: 3
- Source files: 4

## Topics

`pthread_create`, `NULL`, `pthread_attr_destroy`, `pthread_join`, `pthreads`, `rand`, `rand_r`, `pthread_attr_init`, `PTHREAD_CREATE_DETACHED`, `pthread_attr_setdetachstate`, `pthread_attr_getdetachstate`, `pthread_detach`, `pthread_self`, `pthread_mutex_init`, `pthread_mutex_destroy`, `pthread_mutexattr_destroy`, `pthread_mutex_lock`, `pthread_mutex_unlock`, `sigwait`, `pthread_kill`, `pthread_sigmask`, `pthread_cancel`, `PTHREAD_CANCEL_DISABLE`, `PTHREAD_CANCEL_ENABLE`, `PTHREAD_CANCEL_DEFERRED`, `PTHREAD_CANCEL_ASYNCHRONOUS`, `pthread_setcancelstate`, `pthread_exit`, `pthread_cleanup_push`, `pthread_cleanup_pop`, `PTHREAD_CANCELED`, `time`, `clock_getres`

## Tutorial outline

- **Tutorial 3 - Threads, mutexes and signals** - # Tutorial 3 - Threads, mutexes and signals > Introduction notes: > > - Quick look at this material will not suffice, you should compile and run all the programs, check how they work, read > additional materials like man pages. As you read the material please do all the exercises and questions. At t
  - **Thread Management** - ## Thread Management
    - **Creating Threads** - ### Creating Threads A thread is created using the `pthread_create` command. Let's take a look at the declaration of this function: ``` int pthread_create(pthread_t *restrict thread, const pthread_attr_t *restrict attr, void *(*start_routine)(void*), void *restrict arg); ``` Unlike `fork`, this func
    - **Thread Joining** - ### Thread Joining Much like child processes, a thread should also be joined after it finishes its work. This can be achieved using the `pthread_join` command. ``` int pthread_join(pthread_t thread, void **value_ptr); ``` `pthread_join` functions similarly to `wait`, blocking until the thread finish
    - **Excercise** - ### Excercise Goal: Write a program to approximate PI value with Monte Carlo method, program takes the following parameters: - k ... number of threads used to approximate, - n ... number of random tries of each thread. Each thread (except for the main) should conduct its own estimation, at the end t
    - **Solution** - ### Solution **Makefile**: ```makefile CC=gcc CFLAGS=-std=gnu99 -Wall -fsanitize=address,undefined LDFLAGS=-fsanitize=address,undefined LDLIBS=-lpthread ``` Flag `-lpthread` is mandatory for all compilations in this tutorial. Linked library is called libpthread.so (after -l we write the name of the 
    - **Notes and questions** - ### Notes and questions Functions' declarations at the beginning of the code (not the functions definitions) are quite useful, sometimes mandatory. If you do not know the difference please read <a href="http://en.cppreference.com/w/c/language/function_declaration"> this</a>. In multi threaded proces
  - **Detachable threads & Synchronization** - ## Detachable threads & Synchronization
    - **Overview** - ### Overview A detached thread is a thread that you need not join. While it's convenient, it also has downsides, such as not knowing when thread execution ends, as it is not joinable. Because of that, you can't be sure that a thread has actually terminated, which can lead to problems when exiting fr
    - **Spawning a detached thread** - ### Spawning a detached thread In order to spawn a detached thread, you must first create a `pthread_attr_t` object that will later be passed to the `pthread_create` function. In order to initialize one to the default state, you must call `pthread_attr_init`. Then, you have to set its detached state
    - **Detaching a running thread** - ### Detaching a running thread As mentioned above, you may also detach a running thread. You can do it by calling `pthread_detach` with the thread's handle. A thread may detach itself in this way by first obtaining its own handle via a `pthread_self` call, and then calling `pthread_detach`. Attempti
    - **Mutual exclusion** - ### Mutual exclusion Since a detached thread on its own is effectively useless, we are introducing shared state between the threads. It means that two or more threads have to work on the same structure. This is problematic, as we currently have no way of ensuring that a thread won't write to a field
    - **Excercise** - ### Excercise Goal: Write binomial distribution visualization program, use Bean Machine (Galton board) method with 11 bins for bens. The program takes two parameters: - k ... number of beans trowing threads - n ... total number of beans to throw Each thread throws beans separately from others, after
    - **Solution** - ### Solution **prog18.c**: ```c #include <pthread.h> #include <stdio.h> #include <stdlib.h> #include <time.h> #include <unistd.h> #define BIN_COUNT 11 #define NEXT_DOUBLE(seedptr) ((double)rand_r(seedptr) / (double)RAND_MAX) #define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, _
    - **Notes and questions** - ### Notes and questions Once again, all thread input data is passed as pointer to the structure `thrower_args_t`, treads results modify bins array ( pointer in the same structure), no global variables used. In this code two mutexes protect two counters and an array of mutexes protects the bins' arra
  - **Threads and Signals** - ## Threads and Signals
    - **Handling signals** - ### Handling signals When a multithreaded process receives a signal, any one of the threads that haven't blocked the signal may receive it. Another important thing to note is that asynchronous signal handlers (i.e those set by `sigaction`) are not thread-local! Setting a handler in one thread overwr
    - **Sending a signal** - ### Sending a signal Inside your process you may send a signal to a specific thread, using `pthread_kill` ``` int pthread_kill(pthread_t thread, int sig); ``` When you send a signal to a specific thread, only that thread will receive that signal. If the thread is blocking that signal, it will reciev
    - **Setting a signal mask** - ### Setting a signal mask In a multithreaded program you may not use `sigprocmask` to set the signal mask. Instead, you have to call `pthread_sigmask`, which sets the thread-local signal mask. Similar to how processes inherit the mask of the parent, threads inherit the signal mask of the thread that
    - **Excercise** - ### Excercise Goal: The program takes sole 'k' parameter and prints the list of numbers form 1 to k at each second. It must handle two signals in dedicated thread, the following action must be taken upon the signal arrival: - SIGINT (C-c) ... removes random number from the list (do nothing if empty)
    - **Notes and questions** - ### Notes and questions Thread input structure argsSignalHandler_t holds the shared threads data (an array and STOP flag) with protective mutexes and not shared (signal mask and tid of thread designated to handle the signals). How many threads run in this program? **Answer:** Two, main thread create
  - **Thread cancelation** - ## Thread cancelation
    - **Canceling a thread** - ### Canceling a thread A thread can be canceled using the `pthread_cancel` function. This is useful when the program has to exit before it finishes its work, for example due to a signal. More information: ``` man 3p pthread_cancel ```
    - **Setting cancelability** - ### Setting cancelability A thread can choose how it will respond to cancelation requests using the following functions: ``` int pthread_setcancelstate(int state, int *oldstate); int pthread_setcanceltype(int type, int *oldtype); ``` Cancelation requests can be ignored by setting the cancel state to
    - **Cleanup functions** - ### Cleanup functions In a lot of cases, exiting a thread mid-execution leaks resources. This is problematic, especially if a thread is holding a mutex - as it won't be released. To solve this issue, POSIX allows creating cleanup handlers that run when the thread has to exit abruptly. (i.e due to be
    - **Joining canceled threads** - ### Joining canceled threads Canceled threads remain joinable, since a cancel request isn't guaranteed to be processed. If a thread gets canceled, the value pointer passed to `pthread_join` will be set to `PTHREAD_CANCELED` More information: ``` man 3p pthread_join man 3p pthread_exit (specifically 
    - **Excercise** - ### Excercise Goal: Program simulates the faith of MiNI students, it takes the following parameter: - n <= 100 ... count of new students The program stores the counters of students studding on year 1,2,3 and the final BSc year. Main Thread: Initiate students, then for 4 seconds at random intervals (
    - **Notes and questions** - ### Notes and questions Threads receive the pointer to the structure with current year and pointer to years counters, structure argsModify_t does not have the same flow as one in task 2 of this tutorial i.e. program is not making too many unnecessary references to the same data. Structure `studentsL
  - **Source codes presented in this tutorial** - ## Source codes presented in this tutorial - [prog17.c](prog17.c) - [prog18.c](prog18.c) - [prog19.c](prog19.c) - [prog20.c](prog20.c)

## Tasks

- **example1: Laboratory task 3: threads, mutexes, signals** - 4 stages
  1. Creating n+1 threads. Each thread is printing “\*”. Main thread is waiting for all threads.
  2. Main thread is filling the task array and prints it, the processing threads are choosing random array cell number, print its index and exit.
  3. Processing threads are calculating result of one random cell with mutex synchronization, print the result and exit . Main thread is printing both arrays afterwards (after the join). At this stage cells can be calculated more than once but not in parallel.
  4. Each cell is protected by separate mutex. Processing threads are counting remaining cells to compute. If that number reaches 0, threads are terminating otherwise they calculate the next random remaining cell and sleep
- **example2: Laboratory task 3: threads, mutexes, signals** - 4 stages
  1. Create array and mutexes as per task description. After receiving `SIGUSR1`, swaps are performed by the main thread.
  2. Implement printing on `SIGUSR2` using new, detached thread.
  3. Move swapping operation to a separate thread. Implement thread count limit logic.
  4. After receiving `SIGINT` (ctrl+c) program joins all threads and cleanly terminates.
- **example3: Laboratory task 3: threads, mutexes, signals** - 4 stages
  1. Read the arguments, initialize the array. Create dog threads. Each thread increases a random array cell by 1, prints its number, and finishes. After all dog threads finish, the main thread prints the final state of the track.
  2. Implement the logic of the dog thread, initially without locking.
  3. Implement locking using mutexes.
  4. Implement program termination using SIGINT.

## Source files

- `src/prog17.c` (c)
- `src/prog18.c` (c)
- `src/prog19.c` (c)
- `src/prog20.c` (c)
