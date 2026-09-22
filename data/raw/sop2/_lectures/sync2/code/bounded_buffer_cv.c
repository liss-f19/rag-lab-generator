#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <pthread.h>

#define BUFFER_SIZE 10
#define ITERATIONS 20

typedef struct context {
    pthread_mutex_t mtx;
    pthread_cond_t empty;
    pthread_cond_t nonempty;

    int items[BUFFER_SIZE];
    int in;
    int out;
    int size;
} context_t;

#define SHM_SIZE sizeof(context_t)

void producer(context_t *ctx) {
    for (int i = 0; i < ITERATIONS; ++i) {
        struct timespec ts = {0, (rand() % 1000) * 1000000};
        nanosleep(&ts, NULL);

        pthread_mutex_lock(&ctx->mtx);
        while (ctx->size >= BUFFER_SIZE)
            pthread_cond_wait(&ctx->empty, &ctx->mtx);

        int new_item = i;
        ctx->items[ctx->in] = new_item;
        ctx->in = (ctx->in + 1) % BUFFER_SIZE;
        ctx->size++;
        printf("produced '%d'\n", new_item);

      pthread_cond_signal(&ctx->nonempty);
      pthread_mutex_unlock(&ctx->mtx);
    }
}

void consumer(context_t *ctx) {
    for (int i = 0; i < ITERATIONS; ++i) {
        pthread_mutex_lock(&ctx->mtx);
        while (ctx->size == 0)
            pthread_cond_wait(&ctx->nonempty, &ctx->mtx);

        int item = ctx->items[ctx->out];
        ctx->out = (ctx->out + 1) % BUFFER_SIZE;
        ctx->size--;

        printf("consumed '%d'\n", item);

        pthread_cond_signal(&ctx->empty);
        pthread_mutex_unlock(&ctx->mtx);
    }
}


int main() {

    srand(getpid());

    shm_unlink("/sop_shm");

    int fd = shm_open("/sop_shm", O_CREAT | O_EXCL | O_RDWR, 0600);
    if (fd < 0) {
        perror("shm_open()");
        return 1;
    }

    if (ftruncate(fd, SHM_SIZE) < 0) {
        perror("ftruncate()");
        return 1;
    }

    void *ptr = mmap(NULL, SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (ptr == MAP_FAILED) {
        perror("mmap()");
        return 1;
    }

    close(fd);

    context_t *ctx = (context_t *) ptr;
    memset(ctx, 0, sizeof(context_t));

    pthread_mutexattr_t mutex_attr;
    pthread_mutexattr_init(&mutex_attr);
    pthread_mutexattr_setpshared(&mutex_attr, PTHREAD_PROCESS_SHARED);

    pthread_condattr_t cond_attr;
    pthread_condattr_init(&cond_attr);
    pthread_condattr_setpshared(&cond_attr, PTHREAD_PROCESS_SHARED);

    int err;
    printf("Creating mutex and CVs...\n");
    if ((err = pthread_mutex_init(&ctx->mtx, &mutex_attr)) != 0) {
        fprintf(stderr, "pthread_mutex_init(): %s", strerror(err));
        return 1;
    }
    if ((err = pthread_cond_init(&ctx->empty, &cond_attr)) != 0) {
        fprintf(stderr, "pthread_mutex_init(): %s", strerror(err));
        return 1;
    }
    if ((err = pthread_cond_init(&ctx->nonempty, &cond_attr)) != 0) {
        fprintf(stderr, "pthread_mutex_init(): %s", strerror(err));
        return 1;
    }

    switch (fork()) {
        case -1:
            perror("fork()");
            return 1;
        case 0: {
            // child
            consumer(ctx);
            break;
        }
        default: {
            // parent
            producer(ctx);
            while (wait(NULL) > 0);

            pthread_mutex_destroy(&ctx->mtx);
            pthread_cond_destroy(&ctx->empty);
            pthread_cond_destroy(&ctx->nonempty);
            break;
        }
    }

    printf("Unmapping shm\n");
    munmap(ptr, SHM_SIZE);
    return 0;
}
