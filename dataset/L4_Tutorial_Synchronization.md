# Tutorial 4: Synchronization

*Topic: L4 — Synchronization (tutorial)*


Introduction notes:

- Quick look at this material will not suffice, you should compile and run all the programs, check how they work, read additional materials like man pages. As you read the material please do all the exercises and questions. At the end you will find sample task similar to the one you will do during the labs, please do it at home.
- You will find additional information in yellow sections, questions and tasks in blue ones. Under the question you will find the answer, to see it you have to click. Please try to answer on you own before checking.
- Full programs’ codes are placed as attachments at the bottom of this page. On this page only vital parts of the code are displayed
- Codes, information and tasks are organized in logical sequence, in order to fully understand it you should follow this sequence. Sometimes former task makes context for the next one and it is harder to comprehend it without the study of previous parts.
- Most of exercises require command line to practice, I usually assume that all the files are placed in the current working folder and that we do not need to add path parts to file names.
- Quite often you will find `$` sign placed before commands you should run in the shell, obviously you do not need to rewrite this sight to command line, I put it there to remind you that it is a command to execute.
- What you learn and practice in this tutorial will be required for the next ones. If you have a problem with this material after the graded lab you can still ask teachers for help.

## The alarm - Semaphores

Write a multi-threaded timer program. User inputs number of seconds it needs to be counted to the program and awaits response. Program starts separate thread for each new request. The thread sleeps for given time and outputs “Wake up” response. Then the thread exits.

Program has a limit of 5 concurrent threads. If it receives more requests, it outputs immediate response “Only 5 alarms can be set at the time”.

Limit on concurrent threads can be imposed with POSIX semaphore.

Solution `prog21.c`:

```c
#define _GNU_SOURCE
#include <errno.h>
#include <netinet/in.h>
#include <pthread.h>
#include <semaphore.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

#define FS_NUM 5
#define MAX_INPUT 120
volatile sig_atomic_t work = 1;

void sigint_handler(int sig) { work = 0; }

int set_handler(void (*f)(int), int sigNo)
{
    struct sigaction act;
    memset(&act, 0, sizeof(struct sigaction));
    act.sa_handler = f;
    if (-1 == sigaction(sigNo, &act, NULL))
        return -1;
    return 0;
}

struct arguments
{
    int32_t time;
    sem_t *semaphore;
};

void *thread_func(void *arg)
{
    struct arguments *args = (struct arguments *)arg;
    uint32_t tt;
    fprintf(stderr, "Will sleep for %d\n", args->time);
    for (tt = args->time; tt > 0; tt = sleep(tt))
        ;
    puts("Wake up");
    if (sem_post(args->semaphore) == -1)
        ERR("sem_post");
    free(args);
    return NULL;
}

void do_work()
{
    int32_t time;
    pthread_t thread;
    char input[MAX_INPUT];
    struct arguments *args;
    sem_t semaphore;
    if (sem_init(&semaphore, 0, FS_NUM) != 0)
        ERR("sem_init");
    while (work)
    {
        puts("Please enter the number of seconds for the alarm delay:");
        if(fgets(input, MAX_INPUT, stdin) == NULL) {
            if (errno == EINTR)
                continue;
            ERR("fgets:");
        }

        time = atoi(input);
        if(time <= 0) {
            fputs("Incorrect time specified", stderr);
            continue;
        }

        if (TEMP_FAILURE_RETRY(sem_trywait(&semaphore)) == -1)
        {
            switch (errno)
            {
                case EAGAIN:
                    fprintf(stderr, "Only %d alarms can be set at the time.", FS_NUM);
                case EINTR:
                    continue;
            }
            ERR("sem_trywait");
        }

        if ((args = (struct arguments *)malloc(sizeof(struct arguments))) == NULL)
            ERR("malloc:");
        args->time = time;
        args->semaphore = &semaphore;
        if (pthread_create(&thread, NULL, thread_func, (void *) args) != 0)
            ERR("pthread_create");
        if (pthread_detach(thread) != 0)
            ERR("pthread_detach");
    }
}

int main(int argc, char **argv)
{
    if (set_handler(sigint_handler, SIGINT))
        ERR("Seting SIGINT:");
    do_work();
    fprintf(stderr, "Program has terminated.\n");
    return EXIT_SUCCESS;
}
```

It is worth of your time to analyze the above code in aspects not covered here (thread, mutex), please do it as an exercise.

> **Question:** Why it is necessary to allocate memory before we start the thread, can this be avoided?
>
> **Answer:** One common structure is not enough as each thread has to have its own, you can have an array of structures (`FS_NUM` sized) but then you need to manage this array in the way you manage memory so it is easier to allocate a structure on a heap. Naturally this memory has to be released somewhere, in this case, in the thread itself.

> **Question:** What is the semaphore used for?
>
> **Answer:** It keeps the count of threads that can still be started without exceeding `FS_NUM`. Initially its value is set to 5 and before creating next thread it must be decreased by one. Zero value blocks the creation of the threads. Before the thread terminates it increases the semaphore by one.

> **Question:** Why `sem_trywait` is used not just `sem_wait` before the new thread is created? What if we use `sem_wait` instead?
>
> **Answer:** We need to know that we reached the thread limit immediately so we can output deny message. With blocking wait we would wait until one of the threads finishes and increases the semaphore.

> **Question:** What limits the concurrent alarms to 5?
>
> **Answer:** Semaphore, see the questions above.

## Threads pool - conditional variables

Original author: Jerzy Bartuszek

Write a simple program that reads from “/dev/urandom” and writes its content to files. Every time user presses enter, the program reads random bytes and saves it in a file. The program is a multi-threaded application - each request is being handled in a separate thread. Each thread saves random bytes to its own file. Program creates `THREADS_NUM` threads in advance and keeps idle threads in a thread pool. After receiving `SIGINT` server stops accepting user input and terminates its execution after handling all current requests.

Solution `prog22.c`:

```c
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

#define BUFFERSIZE 256
#define READCHUNKS 4
#define THREAD_NUM 3
volatile sig_atomic_t work = 1;

typedef struct
{
    int id;
    int *idlethreads;
    int *condition;
    pthread_cond_t *cond;
    pthread_mutex_t *mutex;
} thread_arg;

void sigint_handler(int sig) { work = 0; }

void set_handler(void (*f)(int), int sigNo)
{
    struct sigaction act;
    memset(&act, 0x00, sizeof(struct sigaction));
    act.sa_handler = f;

    if (-1 == sigaction(sigNo, &act, NULL))
        ERR("sigaction");
}

ssize_t bulk_read(int fd, char *buf, size_t count)
{
    int c;
    size_t len = 0;
    do
    {
        c = TEMP_FAILURE_RETRY(read(fd, buf, count));
        if (c < 0)
            return c;
        if (c == 0)
            return len;
        buf += c;
        len += c;
        count -= c;
    } while (count > 0);
    return len;
}

ssize_t bulk_write(int fd, char *buf, size_t count)
{
    int c;
    size_t len = 0;
    do
    {
        c = TEMP_FAILURE_RETRY(write(fd, buf, count));
        if (c < 0)
            return c;
        buf += c;
        len += c;
        count -= c;
    } while (count > 0);
    return len;
}

void cleanup(void *arg) { pthread_mutex_unlock((pthread_mutex_t *)arg); }

void read_random(int thread_id)
{
    char file_name[20];
    char buffer[BUFFERSIZE];
    snprintf(file_name, sizeof(file_name), "random%d.bin", thread_id);
    printf("Writing to a file %s\n", file_name);
    int i, in, out;
    ssize_t count;
    if ((out = TEMP_FAILURE_RETRY(open(file_name, O_WRONLY | O_CREAT | O_TRUNC | O_APPEND, 0777))) < 0)
        ERR("open");
    if ((in = TEMP_FAILURE_RETRY(open("/dev/urandom", O_RDONLY))) < 0)
        ERR("open");
    for (i = 0; i < READCHUNKS; i++)
    {
        if ((count = bulk_read(in, buffer, BUFFERSIZE)) < 0)
            ERR("bulk_read");
        if ((count = bulk_write(out, buffer, count)) < 0)
            ERR("bulk_write");
        sleep(1);
    }
    if (TEMP_FAILURE_RETRY(close(in)))
        ERR("close");
    if (TEMP_FAILURE_RETRY(close(out)))
        ERR("close");
}

void *thread_func(void *arg)
{
    thread_arg targ;
    memcpy(&targ, arg, sizeof(targ));
    while (1)
    {
        pthread_cleanup_push(cleanup, (void *)targ.mutex);
        if (pthread_mutex_lock(targ.mutex) != 0)
            ERR("pthread_mutex_lock");
        (*targ.idlethreads)++;
        while (!*targ.condition && work)
            if (pthread_cond_wait(targ.cond, targ.mutex) != 0)
                ERR("pthread_cond_wait");
        *targ.condition = 0;
        if (!work)
            pthread_exit(NULL);
        (*targ.idlethreads)--;
        pthread_cleanup_pop(1);
        read_random(targ.id);
    }
    return NULL;
}

void init(pthread_t *thread, thread_arg *targ, pthread_cond_t *cond, pthread_mutex_t *mutex, int *idlethreads,
          int *condition)
{
    int i;
    for (i = 0; i < THREAD_NUM; i++)
    {
        targ[i].id = i + 1;
        targ[i].cond = cond;
        targ[i].mutex = mutex;
        targ[i].idlethreads = idlethreads;
        targ[i].condition = condition;
        if (pthread_create(&thread[i], NULL, thread_func, (void *) &targ[i]) != 0)
            ERR("pthread_create");
    }
}

void do_work(pthread_cond_t *cond, pthread_mutex_t *mutex, const int *idlethreads, int *condition)
{
    char buffer[BUFFERSIZE];
    while (work)
    {
        if (fgets(buffer, BUFFERSIZE, stdin) != NULL)
        {
            if (pthread_mutex_lock(mutex) != 0)
                ERR("pthread_mutex_lock");
            if (*idlethreads == 0)
            {
                if (pthread_mutex_unlock(mutex) != 0)
                    ERR("pthread_mutex_unlock");
                fputs("No threads available\n", stderr);
            }
            else
            {
                if (pthread_mutex_unlock(mutex) != 0)
                    ERR("pthread_mutex_unlock");
                *condition = 1;
                if (pthread_cond_signal(cond) != 0)
                    ERR("pthread_cond_signal");
            }
        }
        else
        {
            if (EINTR == errno)
                continue;
            ERR("fgets");
        }
    }
}

int main(int argc, char **argv)
{
    int i, condition = 0, idlethreads = 0;
    pthread_t thread[THREAD_NUM];
    thread_arg targ[THREAD_NUM];
    pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
    pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
    set_handler(sigint_handler, SIGINT);
    init(thread, targ, &cond, &mutex, &idlethreads, &condition);
    do_work(&cond, &mutex, &idlethreads, &condition);
    if (pthread_cond_broadcast(&cond) != 0)
        ERR("pthread_cond_broadcast");
    for (i = 0; i < THREAD_NUM; i++)
        if (pthread_join(thread[i], NULL) != 0)
            ERR("pthread_join");
    return EXIT_SUCCESS;
}
```

It is worth of your time to analyze the above code in aspects not covered here (thread, mutex), please do it as an exercise.

> **Question:** Can a condition of conditional variable be based on regular variable value?
>
> **Answer:** Yes.

> **Question:** Can a condition of conditional variable be based on a combination of regular variables’ values?
>
> **Answer:** Yes.

> **Question:** Can a condition of conditional variable be based on file content?
>
> **Answer:** Yes.

> **Question:** Can a condition of conditional variable be based on file existence?
>
> **Answer:** Yes.

> **Question:** What are the limitations for the condition of conditional variable?
>
> **Answer:** Everything you can code that will return true or false, coder imagination defines the limit.

> **Question:** Can we use conditional variable without any condition at all?
>
> **Answer:** Yes. it will become a pool of threads waiting for wakening as you need.

> **Question:** Conditional variable must have a mutex, what is protected by it?
>
> **Answer:** Mutex protects the access to the elements (variables,files) used in the variable condition so it remains unchanged when the code tests the condition. You must acquire the mutex prior to changing the state of those elements and prior to condition testing.

> **Question:** Can one mutex protect multiple conditional variables?
>
> **Answer:** It can, but please consider the efficiency and parallelism of your code, it will be lowered.

> **Question:** What are the parts of the condition for the conditional variable in the above code?
>
> **Answer:** The condition is solely based on the variable called “condition”, all threads have access to this variable via pointers.

> **Question:** How does the conditional variable works in this program?
>
> **Answer:** When main thread accepts a new request it sets the “condition” variable to 1 and wakes one of waiting (waiting for the condition) threads. The thread that wakes, checks for “condition==1” and if it is true it handles the request.

> **Question:** Who should check for the condition to be true? The thread that wakes or maybe the one that is being wakened?
>
> **Answer:** The condition must be always checked by the thread being wakened. Even if the one that wakes checked it before it could have changed in meantime as the mutex was released and could have been acquired by some other thread to invalidate the condition! Generally it is better if the condition is checked also before signaling but sometimes it is not possible as wakening thread may not have access to all the condition components.

> **Question:** What is cleanup handler in working thread used for?
>
> **Answer:** It is essential not to end the working thread without releasing the mutex that blocks the conditional (it would freeze entire program) . This handler releases the mutex in case of emergency exit.

## Dice game - barrier

Simulate a following dice game: Each participant rolls a standard six-sided die simultaneously in 10 rounds. After each player rolled, one of the players concludes the round and assigns scores. The player with the highest roll in a given round is awarded one point. In the event of a tie for the highest roll, all tied players receive a point. The game concludes after 10 rounds, and the winner is determined by the player with the highest accumulated points. Represent each player by a thread and use a barrier for the game synchronization.

Solution `prog23.c`:

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include <time.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

#define PLAYER_COUNT 4
#define ROUNDS 10

struct arguments
{
    int id;
    unsigned int seed;
    int* scores;
    int* rolls;
    pthread_barrier_t *barrier;
};

void* thread_func(void *arg) {
    struct arguments *args = (struct arguments *)arg;
    for (int round = 0; round < ROUNDS; ++round) {
        args->rolls[args->id] = 1 + rand_r(&args->seed) % 6;
        printf("player %d: Rolled %d.\n", args->id, args->rolls[args->id]);

        int result = pthread_barrier_wait(args->barrier);

        if(result == PTHREAD_BARRIER_SERIAL_THREAD) {
            printf("player %d: Assigning scores.\n", args->id);
            int max = -1;
            for (int i = 0; i < PLAYER_COUNT; ++i) {
                int roll = args->rolls[i];
                if(roll > max) {
                    max = roll;
                }
            }
            for (int i = 0; i < PLAYER_COUNT; ++i) {
                int roll = args->rolls[i];
                if(roll == max) {
                    args->scores[i] = args->scores[i] + 1;
                    printf("player %d: Player %d got a point.\n", args->id, i);
                }
            }
        }
        pthread_barrier_wait(args->barrier);
    }

    return NULL;
}

void create_threads(pthread_t *thread, struct arguments *targ, pthread_barrier_t *barrier, int *scores, int* rolls)
{
    srand(time(NULL));
    int i;
    for (i = 0; i < PLAYER_COUNT; i++)
    {
        targ[i].id = i;
        targ[i].seed = rand();
        targ[i].scores = scores;
        targ[i].rolls = rolls;
        targ[i].barrier = barrier;
        if (pthread_create(&thread[i], NULL, thread_func, (void *)&targ[i]) != 0)
            ERR("pthread_create");
    }
}

int main() {
    pthread_t threads[PLAYER_COUNT];
    struct arguments targ[PLAYER_COUNT];
    int scores[PLAYER_COUNT] = {0};
    int rolls[PLAYER_COUNT];
    pthread_barrier_t barrier;

    pthread_barrier_init(&barrier, NULL, PLAYER_COUNT);

    create_threads(threads, targ, &barrier, scores, rolls);

    for (int i = 0; i < PLAYER_COUNT; i++) {
        pthread_join(threads[i], NULL);
    }

    puts("Scores: ");
    for (int i = 0; i < PLAYER_COUNT; ++i) {
        printf("ID %d: %i\n", i, scores[i]);
    }

    pthread_barrier_destroy(&barrier);

    return 0;
}
```

> **Question:** How does the barrier works in this program?
>
> **Answer:** It is used to synchronize the threads at two key points within the thread function. The barrier ensures that all participating threads reach a specific point in their execution before allowing any of them to proceed. The barrier is initialized with a count of `PLAYER_COUNT`, which means it will block until `PLAYER_COUNT` threads have called `pthread_barrier_wait`.

> **Question:** Which parts of the thread function are called concurrently?
>
> **Answer:** Each thread independently rolls a six-sided die, and the results are stored in the `args->rolls` array. This part of the code runs concurrently for all threads.

> **Question:** How is the one player thread selected to conclude the round?
>
> **Answer:** The `pthread_barrier_wait` function returns `PTHREAD_BARRIER_SERIAL_THREAD` only for one thread (standard does not specify which one), and 0 for other threads. This mechanism ensures that the action is performed by a single thread in each round, preventing multiple threads from concurrently executing the same code that should only be executed once.

Do the example tasks. During the laboratory you will have more time and a starting code. If you do following tasks in the allotted time, it means that you are well-prepared.
