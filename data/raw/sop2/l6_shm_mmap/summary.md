# Summary: SOP2 lab 6 - Shared memory and mmap

[fake-llm] Summarize the following Operating Systems laboratory for a course knowledge base.
Write at most 250 words covering: what the lab teaches, the POSIX API it exercises, how the tasks are structured and w

---

# SOP2 lab 6 - Shared memory and mmap

Source: https://sop.mini.pw.edu.pl/en/sop2/lab/l6/

- Lab id: `sop2/l6`
- Tutorial sections: 14
- Tasks: 3
- Source files: 5

## Topics

`fork`, `mmap`, `NULL`, `MAP_ANONYMOUS`, `MAP_SHARED`, `MAP_PRIVATE`, `msync`, `munmap`, `ftruncate`, `O_TRUNC`, `shm_open`, `open`, `shm_unlink`, `sem_init`, `pthread_mutex_init`, `pthread_mutex_destroy`, `pthread_mutexattr_init`, `pthread_mutexattr_setpshared`, `pthread_mutexattr_getpshared`, `pthread_mutexattr_setrobust`, `pthread_mutexattr_getrobust`, `pthread_mutex_lock`, `EOWNERDEAD`, `pthread_mutex_consistent`, `pthread_condattr_getpshared`, `pthread_barrierattr_getpshared`, `SIGINT`, `PID`, `pthread_mutexattr_destroy`, `TEMP_FAILURE_RETRY`, `SIGKILL`, `sem_open`, `O_CREAT`, `O_CREATE`

## Tutorial outline

- **Tutorial 6 - Shared memory and mmap** - # Tutorial 6 - Shared memory and mmap
  - **mmap** - ## mmap During past laboratories we went over a few methods of synchronization and data sharing between processes. They always seem more complicated than in the case of threads - where we can simply have shared variables. However, when we use the `fork()` function, the child processes receive their 
    - **Exercise** - ### Exercise Write a program approximating PI using the Monte Carlo method. It takes one argument - `0 < N < 30` - number of calculating processes. Every one performs `100 000` Monte Carlo iterations. The main process maps two areas of memory. The first one is used for sharing the results of child p
    - **Solution** - ### Solution New man pages: ``` man 3p mmap man 2 mmap man 3p munmap man 3p msync man 0p sys_mman.h man 3p ftruncate ``` solution `l6-1.c`: ```c #define _GNU_SOURCE #include <errno.h> #include <fcntl.h> #include <stdio.h> #include <stdlib.h> #include <string.h> #include <sys/mman.h> #include <sys/wa
    - **Notes and questions** - ### Notes and questions - Why isn't synchronisation used? **Answer:** Every child process writes to its own dedicated fragment of shared memory and then the parent joins the results. That's why no conflict is possible and no synchronisation is required. - Why is a `ftruncate` call required? **Answer
  - **Shared memory and robust mutex** - ## Shared memory and robust mutex
    - **shm_*** - ### shm_* In the example above we created an area of memory using `mmap`, which was shared by a group of processes created using `fork()`. What if we wanted the processes to be independent? We can create a named shared memory object, which can be mapped by any process using its unique name. It is ve
    - **Sharing synchronisation objects and the robust mutex** - ### Sharing synchronisation objects and the robust mutex We can synchronise access to shared memory with the tools we already know - pipes, fifo and message queues. However, it's also possible to place semaphores and mutexes in the shared memory, so that all processes have access to them. For semaph
    - **Exercise** - ### Exercise Write two programs - client and server. The server takes one parameter - `3 < N <= 20`. It writes `My PID is: <pid>` to the terminal and creates a 1024 bytes wide segment of shared memory with the name `<pid>-board`. It places in that memory a mutex, `N` and the board - an array of NxN 
    - **Solution** - ### Solution New man pages: ``` man 3p shm_open man 3p shm_unlink man 3p pthread_mutexattr_destroy man 3p pthread_mutexattr_setpshared man 3p pthread_mutexattr_setrobust man 3p pthread_mutex_consistent ``` solution `l6-1_server.c`: ```c #define _GNU_SOURCE #include <errno.h> #include <fcntl.h> #incl
    - **Notes and questions** - ### Notes and questions - Pay attention to the way signals are handled. By using a dedicated thread, the problematic code for signal handling is contained in one function, there are no global variables and we don't have to use `TEMP_FAILURE_RETRY` everywhere. It matters a lot, especially in complex 
  - **Named semaphore** - ## Named semaphore Named semaphores were already mentioned in OPS1, but it's worth to revise. A named semaphore is related to an unnamed one the same way that a fifo is related to a pipe. We create it with the `sem_open` function (see `man 3p sem_open`) passing the `O_CREAT` flag, access rights and 
  - **Source code from the tutorial** - ## Source code from the tutorial - [example2-code.c](example2-code.c) - [l6-1.c](l6-1.c) - [l6-2_client.c](l6-2_client.c) - [l6-2_server.c](l6-2_server.c)
  - **Additional materials** - ## Additional materials Complete the sample exercises. You will have more time and starter code during the lab session, but completing the tasks below on your own means you are well prepared. - [Exercise 1](https://sop.mini.pw.edu.pl/en/sop2/lab/l6/example1/) ~120 minutes - [Exercise 2](https://sop.

## Tasks

- **example1: Task on shared memory and mmap** - 4 stages
  1. Open the file using the mmap function in the parent process. Print its contents to the standard output. The use of streams and the read function is prohibited.
  2. Implement the logic for counting character occurrences in the file. At the end of the program execution, print a summary of how many times each character appeared in the file.
  3. Distribute the workload across N child processes. Move the file opening operation to the child process. Each process should count characters independently of the others. Use shared memory to transfer the computation results to the parent process. The parent process should print the summary after all
  4. Add handling for the case where a child process terminates unexpectedly. In such a case, the parent process should skip printing the summary. Instead, it should print a message stating that the computation failed. Each child process should have a 3% chance of sudden termination when reporting result
- **example2: Task on shared memory and mmap** - 4 stages
  1. Use a named shared memory object for inter-process cooperation. Prepare a shared memory structure containing a process counter protected by a shared mutex. Write a procedure for initializing shared memory with correct counter incrementation when new processes start. To prevent race conditions betwee
  2. Implement three batches of `N` Monte Carlo sample evaluations. Accept program parameters as described in the `usage` function. Use the provided `randomize_points` function to compute one batch of samples. Extend the shared memory structure with two counters describing the number of total samples and
  3. Add handling for the `SIGINT` signal, which interrupts further batch computation. In this stage, the program should continue approximating the integral until it receives the signal. A sufficiently good implementation is to finish computing the current batch and skip taking another one. If the proces
  4. Add handling for process termination while holding a mutex in shared memory outside of the initialization procedure. Change mutexes to be robust and handle the situation when the owner process dies. Upon detecting such a situation, assume that the process counter should be decremented to ensure prop
- **example3: Task on shared memory and mmap** - 4 stages
  1. Implement functions for opening (`channel_open`) and closing (`channel_close`) the channel (a shared memory object). If there is no shared memory object with given name, it should be created and initialized correctly. To eliminate race between `shm_open` and initialization of channel use named semap
  2. Implement function `channel_consume()`. It should wait on `consumer_cv` until channel will change status to `CHANNEL_OCCUPIED`. Then copy data from channel to local memory of process and signal other processes through `producer_cv`. This function should return `0` when it read data correctly. If cha
  3. Implement function `channel_produce()`. It should wait on `producer_cv` until channel will change status to `CHANNEL_EMPTY`. Then copy data from private process memory to `data` field and signal one process through `consumer_cv`. Now instead of printing to standard output put received data to output
  4. Implement duplication logic of input data. > **Check:** > ``` > $ ./ops-generator ops-generator.c ch1 & ./ops-double-processor ch1 ch2 & \ > ./ops-printer ch2 > $ ./ops-generator ops-generator.c ch1 & ./ops-double-processor ch1 ch2 & \ > ./ops-printer ch2 & ./ops-printer ch2 & ./ops-printer ch2 > ``

## Source files

- `src/example2-code.c` (c)
- `src/l6-1.c` (c)
- `src/l6-2_client.c` (c)
- `src/l6-2_server.c` (c)
- `src/sop2l6e3.zip` (zip)
