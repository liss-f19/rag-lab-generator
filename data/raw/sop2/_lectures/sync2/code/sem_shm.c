#include <fcntl.h>
#include <semaphore.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define BUFFER_SIZE 10
#define ITERATIONS 10000000

typedef struct context {
    sem_t done;
    int value;
} context_t;

#define SHM_SIZE sizeof(context_t)

int worker(context_t *ctx) {
    printf("[%d] Worker begins!\n", getpid());

    srand(getpid());

    sleep(1);
    // just any computation
    for (int i = 0; i < ITERATIONS; i++)
    {
        ctx->value = rand() % 1000;
    }

    printf("[%d] Worker computed value = %d!\n", getpid(), ctx->value);
    sem_post(&ctx->done);
    printf("[%d] Worker exits!\n", getpid());
    return 0;
}

int parent(context_t *ctx)
{
    printf("[%d] Parent awaits!\n", getpid());

    sem_wait(&ctx->done);
    printf("[%d] Parent acquired value = %d!\n", getpid(), ctx->value);

    printf("[%d] Parent exits!\n", getpid());
    return 0;
}

int main() {

    srand(getpid());

    void *ptr = mmap(NULL, SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    if (ptr == MAP_FAILED) {
        perror("mmap()");
        return 1;
    }

    context_t* ctx = (context_t*)ptr;
    if (sem_init(&ctx->done, 1, 0) < 0) {
        perror("sem_init()");
        return 1;
    }

    int status;
    switch (fork())
    {
        case -1:
            perror("fork()");
            return 1;
        case 0:
            status = worker(ctx);
            break;
        default:
            status = parent(ctx);
            break;
    }

    munmap(ptr, SHM_SIZE);
    return status;
}
