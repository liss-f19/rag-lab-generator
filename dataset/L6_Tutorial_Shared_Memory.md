# Tutorial 6: Shared memory and mmap

*Topic: L6 — Shared memory and mmap (tutorial)*


## mmap

During past laboratories we went over a few methods of synchronization and data sharing between processes. They always seem more complicated than in the case of threads - where we can simply have shared variables. However, when we use the `fork()` function, the child processes receive their own copy of the parent’s data. Thus, when we modify an array created before the `fork()` call - all changes will occur only within the child process.

It is possible, however, to declare a “mapping” between the program memory and a “memory object”. All changes made in the mapped area will carry over into the mapped “memory object”, managed by the operating system. To create such an object, we use `mmap` (`man 3p mmap`, `man 2 mmap`).

This function has 2 main uses:

- Mapping a file onto an area of memory - it allows us to modify the contents of a file as if it was a simple array.
- Creating an area of memory to be shared with child processes.
- Mapping an area of shared memory (more will be explained in the second part of this tutorial).

Let’s look at the signature of this function:

```c
void *mmap(void *addr, size_t len, int prot, int flags,
           int fildes, off_t off);
```

- `addr` - this parameter allows us to inform the operating system where in memory we want the map to be. In our use cases we pass `NULL` for the system to decide for us.
- `len` - means the size of the memory we want to map.
- `prot` - operations (read/write/execute - see man page) we want to do on the memory - similarly as with files.
- `flags` - this parameter determines the kind of mapping created by `mmap`. The most important flags are described below, read `man 2 mmap` to familiarize yourself with the full list and its details.
  - `MAP_ANONYMOUS` - we create a new anonymous area of memory. When using this flag, the parameter `filedes` should be set to -1. When this flag is not used, the function maps a file by default.
  - `MAP_SHARED` - the resulting mapping can be shared with different processes. In our case we almost always want to use this flag.
  - `MAP_PRIVATE` - the opposite of the former flag - the resulting mapping is not shared, the memory will be copied in the child processes. Not very useful in our case, but still important. Have you ever wondered how `malloc` works?
- `filedes` - descriptor of the file we want to map.
- `off` - offset in the file we want to map. With `MAP_ANONYMOUS` it should always be set to 0.

That’s kind of it - the pointer to memory received from calling `mmap` with the flag `MAP_SHARED` will be usable in any child process and changes made will be visible in all other processes. However, one needs to consider either synchronisation of memory accesses or restricting each process to work only in its own dedicated area of the shared memory.

There are two other functions related to `mmap`:

- `msync` - useful when mapping files, it forces the operating system to modify the underlying file. For the sake of efficiency whenever we modify memory that is mapped to a file, the system won’t immediately apply those changes. It is done this way so that there aren’t many small changes significantly slowing down the system. If we want to make sure that our changes are written to the mapped file, we use `msync`. You can think about it as analogous to `fflush` for streams. See `man 3p msync`.
- `munmap` - mapped memory has to be “unmapped” - that’s what this function is for - see `man 3p munmap`. It’s worth mentioning that with mapped files `munmap` doesn’t guarantee synchronisation - calling `msync` is needed to guarantee that our changes are applied.

### Exercise

Write a program approximating PI using the Monte Carlo method. It takes one argument - 0 < N < 30 - number of calculating processes. Every one performs 100 000 Monte Carlo iterations.

The main process maps two areas of memory. The first one is used for sharing the results of child processes’ calculations. It is N*4 bytes wide. Every child process saves the result of its calculations to one 4-byte cell as a float. The second area of memory maps the file `log.txt`. The main process sets its size to N*8. The child processes save their approximations there in text form. Each one in a single line of width 7 (+eighth symbol `\n`).

### Solution

New man pages:

- `man 3p mmap`
- `man 2 mmap`
- `man 3p munmap`
- `man 3p msync`
- `man 0p sys_mman.h`
- `man 3p ftruncate`

Solution `l6-1.c`:

```c
#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

#define MONTE_CARLO_ITERS 100000
#define LOG_LEN 8

#define ERR(source) \
    (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source), kill(0, SIGKILL), exit(EXIT_FAILURE))

void child_work(int n, float* out, char* log)
{
    int sample = 0;
    srand(getpid());
    int iters = MONTE_CARLO_ITERS;
    while (iters-- > 0)
    {
        double x = ((double)rand()) / RAND_MAX, y = ((double)rand()) / RAND_MAX;
        if (x * x + y * y <= 1.0)
            sample++;
    }
    out[n] = ((float)sample) / MONTE_CARLO_ITERS;
    char buf[LOG_LEN + 1];

    snprintf(buf, LOG_LEN + 1, "%7.5f\n", out[n] * 4.0f);
    memcpy(log + n * LOG_LEN, buf, LOG_LEN);
}

void parent_work(int n, float* data)
{
    pid_t pid;
    double sum = 0.0;
    for (;;)
    {
        pid = wait(NULL);
        if (pid <= 0)
        {
            if (errno == ECHILD)
                break;
            ERR("waitpid");
        }
    }
    for (int i = 0; i < n; i++)
        sum += data[i];
    sum = sum / n;

    printf("Pi is approximately %f\n", sum * 4);
}

void create_children(int n, float* data, char* log)
{
    while (n-- > 0)
    {
        switch (fork())
        {
            case 0:
                child_work(n, data, log);
                exit(EXIT_SUCCESS);
            case -1:
                perror("Fork:");
                exit(EXIT_FAILURE);
        }
    }
}

void usage(char* name)
{
    fprintf(stderr, "USAGE: %s n\n", name);
    fprintf(stderr, "10000 >= n > 0 - number of children\n");
    exit(EXIT_FAILURE);
}

int main(int argc, char** argv)
{
    int n;
    if (argc != 2)
        usage(argv[0]);
    n = atoi(argv[1]);
    if (n <= 0 || n > 30)
        usage(argv[0]);

    int log_fd;
    if ((log_fd = open("./log.txt", O_CREAT | O_RDWR | O_TRUNC, -1)) == -1)
        ERR("open");
    if (ftruncate(log_fd, n * LOG_LEN))
        ERR("ftruncate");
    char* log;
    if ((log = (char*)mmap(NULL, n * LOG_LEN, PROT_WRITE | PROT_READ, MAP_SHARED, log_fd, 0)) == MAP_FAILED)
        ERR("mmap");
    if (close(log_fd))
        ERR("close");
    float* data;
    if ((data = (float*)mmap(NULL, n * sizeof(float), PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0)) ==
        MAP_FAILED)
        ERR("mmap");

    create_children(n, data, log);
    parent_work(n, data);

    if (munmap(data, n * sizeof(float)))
        ERR("munmap");
    if (msync(log, n * LOG_LEN, MS_SYNC))
        ERR("msync");
    if (munmap(log, n * LOG_LEN))
        ERR("munmap");

    return EXIT_SUCCESS;
}
```

### Notes and questions

> **Question:** Why isn’t synchronisation used?
>
> **Answer:** Every child process writes to its own dedicated fragment of shared memory and then the parent joins the results. That’s why no conflict is possible and no synchronisation is required.

> **Question:** Why is a `ftruncate` call required?
>
> **Answer:** Without it the `log.txt` file would be size 0, because it’s opened with the `O_TRUNC` flag, which causes the function to remove the file’s contents. Otherwise, if the flag wouldn’t have been added, the size would have been dependent on the earlier contents, which would have been unpredictable.

## Shared memory and robust mutex

### shm_*

In the example above we created an area of memory using `mmap`, which was shared by a group of processes created using `fork()`. What if we wanted the processes to be independent? We can create a named shared memory object, which can be mapped by any process using its unique name. It is very similar and analogous in their differences to the pair: pipe - FIFO, which was introduced in L5.

To create a named shared memory object use `shm_open` (see `man 3p shm_open`). Its usage is very simple, and the parameters are analogous to regular `open` or `mq_open`, so reading the man page should explain it.

`shm_open` returns a descriptor, which behaves very similarly to a file descriptor. Initially the created memory is of size zero, so it is required to increase it with e.g. `ftruncate`. Then simply use the function `mmap`.

When all processes are done using the shared memory it should be deleted using the `shm_unlink` function. It is also a very simple function, so just check `man 3p shm_unlink`.

### Sharing synchronisation objects and the robust mutex

We can synchronise access to shared memory with the tools we already know - pipes, fifo and message queues. However, it’s also possible to place semaphores and mutexes in the shared memory, so that all processes have access to them.

For semaphores it’s easy: see `man 3p sem_init`. If the second parameter `pshared` is set to a value other than zero, the semaphore can be used across processes. It’s enough, then, to choose an area of the shared memory of size `sizeof(sem_t)`, initialise a semaphore that way and all processes will be able to use it.

Sharing mutexes is a little harder. Setting the special properties of a mutex is also done during initialisation (`pthread_mutex_init`, but see `man 3p pthread_mutex_destroy`) - we can pass special attributes as the second parameter, `pthread_mutexattr_init`. Then, for the mutex to be shared between processes, a mutex attribute object should be created (`pthread_mutexattr_init`), `pthread_mutexattr_setpshared` should be called (see `man 3p pthread_mutexattr_getpshared`), and finally those attributes should be passed to `pthread_mutex_init`.

A mutex created this way will be shared between processes correctly, but it is not the end of our troubles. The basic limitation of the mutex having to be unlocked in the same thread that locked it is still in power. It creates a problem whenever a process terminates due to an error after locking the mutex and before unlocking it. The robust mutex solves this problem.

Creating a robust mutex requires passing the appropriate attribute set with `pthread_mutexattr_setrobust` (see `man 3p pthread_mutexattr_getrobust`) - similarly to sharing. When we attempt to lock (`pthread_mutex_lock`) a mutex in an invalid state (locked by a process that terminated already) we will get the `EOWNERDEAD` error (see `man 3p pthread_mutex_lock`), but the mutex will get locked anyway. To repair the mutex state `pthread_mutex_consistent` (`man 3p pthread_mutex_consistent`) needs to be called.

Condition variables and barriers are initialised similarly. They can also be shared between processes when appropriate attributes are set. See `man 3p pthread_condattr_getpshared` and `man 3p pthread_barrierattr_getpshared`. Those objects thankfully don’t have additional problems that need to be addressed like in the mutex case.

See how shared memory and mutexes were used in the exercise below.

### Exercise

Write two programs - client and server. The server takes one parameter - 3 < N <= 20. It writes `My PID is: <pid>` to the terminal and creates a 1024 bytes wide segment of shared memory with the name `<pid>-board`. It places in that memory a mutex, N and the board - an array of NxN bytes. The board is filled with random numbers from the [1,9] range. Every 3 seconds it displays the board’s state to the terminal. After receiving `SIGINT` it displays the board one last time and terminates.

The client program takes one parameter - PID of the server. It opens the memory created by the server. Then it follows the instructions:

1. Lock the mutex.
2. Pick a random number from the [1,10] range. If 1 is picked, it prints `Oops...` and terminates.
3. Pick 2 numbers x and y from 0 to N-1 and writes `trying to search field (x,y)` to the terminal.
4. Check what number is on the board under (x,y).
5. If it’s not zero, add the number to your score, write `found <P> points` to the terminal, zero that board space, unlock the mutex, wait a second and go back to step 1
6. If it’s zero, the program unlocks the mutex, writes `GAME OVER: score <X>` (where X is the score) to the terminal and terminates.

### Solution

New man pages:

- `man 3p shm_open`
- `man 3p shm_unlink`
- `man 3p pthread_mutexattr_destroy`
- `man 3p pthread_mutexattr_setpshared`
- `man 3p pthread_mutexattr_setrobust`
- `man 3p pthread_mutex_consistent`

Solution `l6-1_server.c`:

```c
#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define ERR(source) \
    (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source), kill(0, SIGKILL), exit(EXIT_FAILURE))

#define SHM_SIZE 1024

void usage(char* name)
{
    fprintf(stderr, "USAGE: %s N\n", name);
    fprintf(stderr, "3 < N <= 30 - board size\n");
    exit(EXIT_FAILURE);
}

typedef struct
{
    int running;
    pthread_mutex_t mutex;
    sigset_t old_mask, new_mask;
} sighandling_args_t;

void* sighandling(void* args)
{
    sighandling_args_t* sighandling_args = (sighandling_args_t*)args;
    int signo;
    if (sigwait(&sighandling_args->new_mask, &signo))
        ERR("sigwait failed.");
    if (signo != SIGINT)
    {
        ERR("unexpected signal");
    }

    pthread_mutex_lock(&sighandling_args->mutex);
    sighandling_args->running = 0;
    pthread_mutex_unlock(&sighandling_args->mutex);
    return NULL;
}

int main(int argc, char* argv[])
{
    if (argc != 2)
        usage(argv[0]);

    const int N = atoi(argv[1]);
    if (N < 3 || N >= 100)
        usage(argv[0]);

    const pid_t pid = getpid();
    srand(pid);

    printf("My PID is %d\n", pid);
    int shm_fd;
    char shm_name[32];
    sprintf(shm_name, "/%d-board", pid);

    if ((shm_fd = shm_open(shm_name, O_CREAT | O_EXCL | O_RDWR, 0666)) == -1)
        ERR("shm_open");
    if (ftruncate(shm_fd, SHM_SIZE) == -1)
        ERR("ftruncate");

    char* shm_ptr;
    if ((shm_ptr = (char*)mmap(NULL, SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0)) == MAP_FAILED)
        ERR("mmap");

    pthread_mutex_t* mutex = (pthread_mutex_t*)shm_ptr;
    char* N_shared = (shm_ptr + sizeof(pthread_mutex_t));
    char* board = (shm_ptr + sizeof(pthread_mutex_t)) + 1;
    N_shared[0] = N;

    for (int i = 0; i < N; i++)
    {
        for (int j = 0; j < N; j++)
        {
            board[i * N + j] = 1 + rand() % 9;
        }
    }

    pthread_mutexattr_t mutex_attr;
    pthread_mutexattr_init(&mutex_attr);
    pthread_mutexattr_setpshared(&mutex_attr, PTHREAD_PROCESS_SHARED);
    pthread_mutexattr_setrobust(&mutex_attr, PTHREAD_MUTEX_ROBUST);
    pthread_mutex_init(mutex, &mutex_attr);

    sighandling_args_t sighandling_args = {1, PTHREAD_MUTEX_INITIALIZER};

    sigemptyset(&sighandling_args.new_mask);
    sigaddset(&sighandling_args.new_mask, SIGINT);
    if (pthread_sigmask(SIG_BLOCK, &sighandling_args.new_mask, &sighandling_args.old_mask))
        ERR("SIG_BLOCK error");

    pthread_t sighandling_thread;
    pthread_create(&sighandling_thread, NULL, sighandling, &sighandling_args);

    while (1)
    {
        pthread_mutex_lock(&sighandling_args.mutex);
        if (!sighandling_args.running)
            break;

        pthread_mutex_unlock(&sighandling_args.mutex);

        int error;
        if ((error = pthread_mutex_lock(mutex)) != 0)
        {
            if (error == EOWNERDEAD)
            {
                pthread_mutex_consistent(mutex);
            }
            else
            {
                ERR("pthread_mutex_lock");
            }
        }

        for (int i = 0; i < N; i++)
        {
            for (int j = 0; j < N; j++)
            {
                printf("%d", board[i * N + j]);
            }
            putchar('\n');
        }
        putchar('\n');
        pthread_mutex_unlock(mutex);
        struct timespec t = {3, 0};
        nanosleep(&t, &t);
    }

    pthread_join(sighandling_thread, NULL);

    pthread_mutexattr_destroy(&mutex_attr);
    pthread_mutex_destroy(mutex);

    munmap(shm_ptr, SHM_SIZE);
    shm_unlink(shm_name);

    return EXIT_SUCCESS;
}
```

Solution `l6-1_client.c`:

```c
#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define ERR(source) \
    (fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), perror(source), kill(0, SIGKILL), exit(EXIT_FAILURE))

#define SHM_SIZE 1024

void usage(char* name)
{
    fprintf(stderr, "USAGE: %s server_pid\n", name);
    exit(EXIT_FAILURE);
}

int main(int argc, char* argv[])
{
    if (argc != 2)
        usage(argv[0]);

    const int server_pid = atoi(argv[1]);
    if (server_pid == 0)
        usage(argv[0]);

    srand(getpid());

    int shm_fd;
    char shm_name[32];
    sprintf(shm_name, "/%d-board", server_pid);

    if ((shm_fd = shm_open(shm_name, O_RDWR, 0666)) == -1)
        ERR("shm_open");

    char* shm_ptr;
    if ((shm_ptr = (char*)mmap(NULL, SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0)) == MAP_FAILED)
        ERR("mmap");

    pthread_mutex_t* mutex = (pthread_mutex_t*)shm_ptr;
    char* N_shared = (shm_ptr + sizeof(pthread_mutex_t));
    char* board = (shm_ptr + sizeof(pthread_mutex_t)) + 1;
    const int N = N_shared[0];

    int score = 0;
    while (1)
    {
        int error;
        if ((error = pthread_mutex_lock(mutex)) != 0)
        {
            if (error == EOWNERDEAD)
            {
                pthread_mutex_consistent(mutex);
            }
            else
            {
                ERR("pthread_mutex_lock");
            }
        }

        const int D = 1 + rand() % 9;
        if (D == 1)
        {
            printf("Ops...\n");
            exit(EXIT_SUCCESS);
        }

        int x = rand() % N, y = rand() % N;
        printf("trying to search field (%d,%d)\n", x, y);
        const int p = board[N * y + x];
        if (p == 0)
        {
            printf("GAME OVER: score %d\n", score);
            pthread_mutex_unlock(mutex);
            break;
        }
        else
        {
            printf("found %d points\n", p);
            score += p;
            board[N * y + x] = 0;
        }

        pthread_mutex_unlock(mutex);
        struct timespec t = {1, 0};
        nanosleep(&t, &t);
    }

    munmap(shm_ptr, SHM_SIZE);

    return EXIT_SUCCESS;
}
```

### Notes and questions

Pay attention to the way signals are handled. By using a dedicated thread, the problematic code for signal handling is contained in one function, there are no global variables and we don’t have to use `TEMP_FAILURE_RETRY` everywhere. It matters a lot, especially in complex projects.

> **Question:** If not for the random termination of the client processes, would the robust mutex still be needed?
>
> **Answer:** Yes, the process could still terminate here e.g. by receiving a `SIGKILL`. Generally when sharing a mutex with different processes, it’s best to always make it robust.

> **Question:** Does the robust mutex make it so that a deadlock due to an error is impossible?
>
> **Answer:** Unfortunately no. The process can still fail to release a mutex or have a different error. Note the special case where a process unmaps the shared memory before releasing the mutex. The “robustness” doesn’t work here!

> **Question:** Why is a call to `ftruncate` required?
>
> **Answer:** A shared memory object is zero-sized when created and has to be resized.

## Named semaphore

Named semaphores were already mentioned in OPS1, but it’s worth to revise. A named semaphore is related to an unnamed one the same way that a fifo is related to a pipe. We create it with the `sem_open` function (see `man 3p sem_open`) passing the `O_CREAT` flag, access rights and an initial value. E.g.:

```c
sem_t *semaphore = sem_open("OPS-semaphore", O_CREAT, 0666, 5);
```

Will create a semaphore with the name SOP-semaphore and initialise it with a value of 5. Calling the function with the same parameters (or without `O_CREATE`: `sem_open("OPS-semaphore", 0);`) in another process will return the same, existing semaphore. As you can see it’s analogous to fifo and message queues.

Thanks to their simplicity, named semaphores are great for the synchronisation of processes sharing memory. When a few independent processes want to use a single object only one is going to initialise it. It’s important for the other processes to wait until the initialisation is done - which can be accomplished simply with a semaphore.
