# Summary: SOP1 lab 4 - Synchronization

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP1 lab 4 - Synchronization

Source: https://sop.mini.pw.edu.pl/en/sop1/lab/l4/

- Lab id: `sop1/l4`
- Tutorial sections: 5
- Tasks: 3
- Source files: 5

## Topics

`perror`, `fprintf`, `exit`, `sigint_handler`, `set_handler`, `memset`, `sigaction`, `thread_func`, `sleep`, `puts`, `sem_post`, `free`, `do_work`, `sem_init`, `fgets`, `atoi`, `fputs`, `sem_trywait`, `malloc`, `pthread_create`, `pthread_detach`, `bulk_read`, `read`, `bulk_write`, `write`, `cleanup`, `pthread_mutex_unlock`, `read_random`, `snprintf`, `printf`, `open`, `close`, `memcpy`, `pthread_cleanup_push`, `pthread_mutex_lock`, `pthread_cond_wait`, `pthread_exit`, `pthread_cleanup_pop`, `init`, `pthread_cond_signal`, `pthread_cond_broadcast`, `pthread_join`, `rand_r`, `pthread_barrier_wait`, `create_threads`, `srand`, `time`, `rand`, `pthread_barrier_init`, `pthread_barrier_destroy`

## Tutorial outline

- **Tutorial 4 - Synchronization** - # Tutorial 4 - Synchronization > Introduction notes: > > - Quick look at this material will not suffice, you should compile and run all the programs, check how they work, read additional materials like man pages. As you read the material please do all the exercises and questions. At the end you will
  - **The alarm - Semaphores** - ## The alarm - Semaphores Write a multi-threaded timer program. User inputs number of seconds it needs to be counted to the program and awaits response. Program starts separate thread for each new request. The thread sleeps for given time and outputs "Wake up" response. Then the thread exits. Progra
  - **Threads pool - conditional variables** - ## Threads pool - conditional variables Original author: **Jerzy Bartuszek** Write a simple program that reads from "/dev/urandom" and writes its content to files. Every time user presses enter, the program reads random bytes and saves it in a file. The program is a multi-threaded application - each
  - **Dice game - barrier** - ## Dice game - barrier Simulate a following dice game: Each participant rolls a standard six-sided die simultaneously in 10 rounds. After each player rolled, one of the players concludes the round and assigns scores. The player with the highest roll in a given round is awarded one point. In the even
  - **Source codes presented in this tutorial** - ## Source codes presented in this tutorial - [prog21.c](prog21.c) - [prog22.c](prog22.c) - [prog23.c](prog23.c)

## Tasks

- **example1: Laboratory task 4: synchronization** - 5 stages
  1. Main thread reads csv header and file size and divides it into m chunks. It creates n threads. Each thread is printing "*" and exits. (3p.)
  2. Implemented thread pool. Threads take one available chunk task and prints assigned chunk(start and size in bytes) until there is no chunk tasks left. Main thread exits when there is no more tasks. (4p)
  3. Processing threads are all reading assigned chunks and saving read lines into linked lists. (3p)
  4. When thread encounters an error it waits for all currently running threads, checks the line number of the error and prints it to stderr. The processing stops and the program exits. (4p)
  5. One thread is concatenating resulting linked lists and prints it line by line to stdout. (2p)
- **example2: Laboratory task 4: synchronization** - 4 stages
  1. The host creates `n` threads. Each thread is dealt 7 cards. Each thread prints its hand and exits. The host waits for all threads and exits.
  2. The host waits for `SIGUSR1` signal and properly tries to seat a new player. The player prints their hand and waits for other players at the table. When all the players gather, they all exit, and the table is available for the subsequent group of players.
  3. The players play the game according to the rules. **Hint**: Barrier could be used to synchronize the stages of the game.
  4. Termination of the program by `C-c` works, all threads waiting or playing immediately leave, and all resources are properly cleaned up. **Hint**: A conditional variable could be used to notify players waiting at the table to either leave or start the game.
- **example3: Laboratory task 4: synchronization** - 4 stages
  1. Implement the `initialize` function. Created threads should print their `TID` and wait on a conditional variable.
  2. Implement the `dispatch` function. The `hello` option should work at this stage.
  3. Implement passing data to calculate the area of a circle and synchronization with the threads drawing points. The `circle` option should work at this stage.
  4. Implement the `cleanup` function. The program should wait for the calculations to finish and correctly terminate all threads when choosing the `exit` option.

## Source files

- `src/prog21.c` (c)
- `src/prog22.c` (c)
- `src/prog23.c` (c)
- `src/sop1l4e2.zip` (zip)
- `src/sop1l4e3.zip` (zip)
