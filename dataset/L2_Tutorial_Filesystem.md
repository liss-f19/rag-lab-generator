# Tutorial 2: Filesystem

*Topic: L2 — Filesystem (tutorial)*


## Low-Level File Operations

You can also use low-level functions to read and write files - functions provided directly by the operating system rather than by the C standard library. With these functions, you can, for instance, send packets over a network, which we’ll cover in the next semester.

Instead of using `FILE` pointers, low-level functions work with file descriptors (fd) - integer values that identify resources within a process. In this case, these will be files, but in general, they can refer to various system resources. To use the functions below, include the headers `<fcntl.h>` and `<unistd.h>`.

```c
int open(const char *path, int oflag, ...);
```

See `man 3p open`.

- `path` - path to the file being opened,
- `oflag` - flags for opening the file, combined with a bitwise OR `|`, similar to the mode used in `fopen` but also specifying behavior in various edge cases. See `man 3p open` for the full list. Important flags for the lab include:
  - an access mode, e.g. `O_RDONLY`, `O_WRONLY`, or `O_RDWR`
  - `O_CREAT` - create the file if it does not exist
  - `O_EXCL` - used with `O_CREAT`: create the file if it does not exist, or return an error if it already exists
  - `O_APPEND` - append data to the end of the file
  - `O_TRUNC` - truncate the file to zero length when opening it
  - `O_NONBLOCK` - open in nonblocking mode: `read` and `write` do not wait for data to become available or for space to write it
- `...` - a third argument may be needed when creating a file; it specifies the permissions.

This function returns a file descriptor `fd`, which we’ll use with the following functions. A descriptor is a process resource, so it must be released with `close` (`man 3p close`) after use.

Low-level functions don’t use buffering. `read` (see `man 3p read`) receives characters as soon as they’re available. This means it doesn’t always read as many characters as we expect. On one hand, we get data as quickly as possible without waiting for the system to load the rest from the disk. On the other hand, we need to make sure we actually read all the data we want.

```c
ssize_t read(int fildes, void *buf, size_t nbyte);
```

- `fildes` - file descriptor obtained from `open`,
- `buf` - pointer to the buffer where data will be stored,
- `nbyte` - size of the data the function is expected to read.

This function returns the number of bytes successfully read.

The `write` function works similarly (see `man 3p write`):

```c
ssize_t write(int fildes, const void *buf, size_t nbyte);
```

- `fildes` - file descriptor obtained from `open`,
- `buf` - pointer to the buffer containing the data,
- `nbyte` - size of the data to be sent.

The return value indicates the number of bytes successfully written.

These functions read or write data sequentially. Sometimes, however, we need to access data somewhere in the middle of a file. We could read enough bytes to reach it, but that would be inefficient. The `lseek` function (`man 3p lseek`) lets us move the file position directly:

```c
off_t lseek(int fildes, off_t offset, int whence);
```

The `whence` parameter can be `SEEK_SET` (set the position relative to the beginning of the file), `SEEK_CUR` (relative to the current position), or `SEEK_END` (relative to the end of the file). Since `lseek` returns the position after the operation, calling it with 0 and `SEEK_CUR` gives the current position in the file.

When browsing the manuals, you may have noticed counterparts of familiar functions with an `-at` suffix, such as `fstatat`, `openat`, and `symlinkat`. These functions usually take an additional parameter: a file descriptor relative to which paths are resolved. They can make programming more convenient by avoiding the need to construct long relative paths or change the working directory.

### Task

Write a simple program that copies files. It should accept two paths as arguments and copy the file from the first path to the second.

This time, use low-level functions.

### Task Solution

What the student needs to know:

- `man 3p open`
- `man 3p close`
- `man 3p read`
- `man 3p write`
- `man 3p mknod` (only constants describing permissions for `open`)

Code for file `l2-1.c`:

```c
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

#define FILE_BUF_LEN 256

void usage(const char *const pname)
{
    fprintf(stderr, "USAGE:%s path_1 path_2\n", pname);
    exit(EXIT_FAILURE);
}

int main(const int argc, const char *const *const argv)
{
    if (argc != 3)
        usage(argv[0]);

    const char *const path_1 = argv[1];
    const char *const path_2 = argv[2];

    const int fd_1 = open(path_1, O_RDONLY);
    if (fd_1 == -1)
        ERR("open");

    const int fd_2 = open(path_2, O_WRONLY | O_CREAT, 0777);
    if (fd_2 == -1)
        ERR("open");

    char file_buf[FILE_BUF_LEN];
    for (;;)
    {
        const ssize_t read_size = read(fd_1, file_buf, FILE_BUF_LEN);
        if (read_size == -1)
            ERR("read");

        if (read_size == 0)
            break;

        if (write(fd_2, file_buf, read_size) == -1)
            ERR("write");
    }

    if (close(fd_2) == -1)
        ERR("close");

    if (close(fd_1) == -1)
        ERR("close");

    return EXIT_SUCCESS;
}
```

### Notes and Questions

> **Question:** Could this program be implemented using the standard C library functions instead of low-level I/O (e.g., `fopen`, `fprintf`, etc.)?
>
> **Answer:** Yes, there’s nothing in this program that prevents us from using the functions shown earlier.

> **Question:** Can we write data to a file descriptor returned by `open` using `fprintf`?
>
> **Answer:** No! Functions like `fprintf`, `fgets`, and `fscanf` accept a `FILE*` variable as an argument, while a file descriptor is an `int` used by the operating system to identify an open file.

## Vectorized File Operations

The `writev` function (see `man 3p writev`) provides a convenient solution when the data we want to write isn’t in a single continuous memory fragment. It allows us to gather data from multiple locations and write it to a file with a single function call. It’s defined in `<sys/uio.h>`.

```c
ssize_t writev(int fildes, const struct iovec *iov, int iovcnt);
```

- `fildes` - descriptor to which data is written,
- `iov` - array of structures describing the buffers from which data is gathered - `struct iovec` (see `man 0p sys_uio.h`), which has the following fields:
  ```
  void   *iov_base -> pointer to the memory area
  size_t  iov_len  -> length of the memory area
  ```
- `iovcnt` - size of the `iov` array.

This function writes to `fildes`:

- `iov[0].iov_len` bytes starting from `iov[0].iov_base`,
- `iov[1].iov_len` bytes starting from `iov[1].iov_base`, … up to
- `iov[iovcnt-1].iov_len` bytes starting from `iov[iovcnt-1].iov_base`.

The `readv` function works similarly (see `man 3p readv`):

```c
ssize_t readv(int fildes, const struct iovec *iov, int iovcnt);
```

- `fildes` - descriptor from which data is read,
- `iov` - array of `struct iovec` structures describing the buffers into which data is scattered,
- `iovcnt` - size of the `iov` array.

In other aspects, these functions work analogously to their non-vector counterparts `write` and `read`.

### Task

The file `database` contains a catalog of library books in binary format. It consists of 68-byte records: 4 bytes of the book file’s size (`unsigned int`) and 64 bytes of title, padded with zeros if shorter. The number of records can be computed from the file size.

Write a program that takes the database path and an output file path as arguments. The program should read the database with a single `readv` call into an array of structures with fields `unsigned int size` and `char title[65]` (the extra byte lets us always terminate the title with a zero) and print each book in the format `Size: <size>, Title: <title>`. Then it should increase the size of each book by 1 and write the modified database to the output file with a single `writev` call, using the same buffers.

### Task Solution

What the student needs to know:

- `man 3p writev`
- `man 3p readv`
- `man 0p sys_uio.h`

Code for file `l2-v.c`:

```c
#define _POSIX_C_SOURCE 200809L

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <unistd.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

typedef struct
{
    unsigned int size;
    char title[65];
} Book;

void usage(const char* pname)
{
    fprintf(stderr, "USAGE:%s database output\n", pname);
    exit(EXIT_FAILURE);
}

int main(int argc, char** argv)
{
    if (argc != 3)
        usage(argv[0]);

    int fd = open(argv[1], O_RDONLY);
    if (fd < 0)
        ERR("open");
    struct stat s;
    if (fstat(fd, &s) < 0)
        ERR("fstat");
    const int size = s.st_size;
    const int N = size / 68;

    struct iovec* buffers = malloc(N * sizeof(struct iovec));
    Book* books = malloc(N * sizeof(Book));
    if (buffers == NULL || books == NULL)
        ERR("malloc");

    for (int i = 0; i < N; i++)
    {
        buffers[i].iov_base = &books[i];
        buffers[i].iov_len = 68;
        books[i].title[64] = 0;
    }
    if (readv(fd, buffers, N) < size)
        ERR("readv");
    if (close(fd))
        ERR("close");

    for (int i = 0; i < N; i++)
    {
        printf("Size: %u Title: %s\n", books[i].size, books[i].title);
        books[i].size++;
    }

    if ((fd = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0644)) < 0)
        ERR("open");
    if (writev(fd, buffers, N) < size)
        ERR("writev");
    if (close(fd))
        ERR("close");

    free(buffers);
    free(books);
    return EXIT_SUCCESS;
}
```

## Mmap

Another very convenient way to access a file is to map it into memory. The `mmap` function does this. It is also widely used for many other purposes, which we will discuss later. For now, we will focus only on mapping files. It usually looks like this:

```c
#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

void create_file()
{
    int fd = open("a.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd == -1)
        ERR("open");
    char *data = "abcdefghijklmnopqrstuvwxyz\n";
    if (write(fd, data, strlen(data)) < 0)
        ERR("write");
    close(fd);
}

int main(void)
{
    create_file();

    int fd = open("a.txt", O_RDWR);
    if (fd == -1)
        ERR("open");

    struct stat sb;
    if (fstat(fd, &sb) == -1)
        ERR("fstat");
    size_t length = sb.st_size;
    char *buff = mmap(NULL, length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (buff == MAP_FAILED)
        ERR("mmap");

    printf("a.txt[3] = %c (ASCII: %d)\n", buff[3], buff[3]);
    buff[3] = 'Z';
    msync(buff, length, MS_SYNC);

    munmap(buff, length);
    close(fd);
    return 0;
}
```

The most important function here is, of course, `mmap` itself:

```c
char *buff = mmap(NULL, length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
```

Here we ask the operating system to map the file identified by `fd` into a memory region of size `length`, so that we can both read and modify it (`PROT_READ | PROT_WRITE`). The result is a pointer to the mapped memory, or `MAP_FAILED` if an error occurs. You can read about the other parameters and uses of this function in the manual (`man 3p mmap`, or `man 2 mmap` for Linux extensions), but they will not be required in the lab.

For now, the important point is that, as the code above shows, `mmap` lets us modify files conveniently, just like ordinary arrays. Two helper functions are `msync` and `munmap`. `msync` requests synchronization of changes to disk; the operating system does not always do this immediately because disk writes are slow. `munmap` removes the mapping as part of cleanup.

One important point is that the descriptor must have the appropriate access mode. If we passed `PROT_READ | PROT_WRITE` to `mmap` together with a descriptor opened with `O_RDONLY`, for example, the function would return an error.

## Blocking and Nonblocking Operations and fcntl

In the description of `open`, we mentioned the `O_NONBLOCK` flag, which lets us open a file in nonblocking mode. By default, files are opened in blocking mode (remember that we are working with POSIX systems, where “everything is a file”). A call to `read` or `write` on such a descriptor may wait until data is available to read or space is available to write.

The terminal and functions such as `scanf` and `getchar` are examples of this behavior. When we call them, program execution stops until we provide some input on the terminal. If we switch stdin to nonblocking mode, however, operations on it return immediately; consider the following example:

```c
#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

void set_nonblocking(int fd)
{
    int flags = fcntl(fd, F_GETFL);
    if (flags == -1)
        ERR("fcntl");
    flags |= O_NONBLOCK;
    if (fcntl(fd, F_SETFL, flags) == -1)
        ERR("fcntl");
}

int main(void)
{
    char buf[128];
    ssize_t n;

    puts("Testing blocking scanf - type something and press enter:");
    scanf("%100s", buf);
    printf("You typed: %s\n", buf);

    puts("Testing blocking read - type something and press enter:");
    n = read(STDIN_FILENO, buf, sizeof(buf) - 1);
    if (n < 0)
        ERR("read");
    buf[n] = 0;
    printf("Got %lu bytes: \"%s\"\n", n, buf);
    if (buf[n - 1] == '\n')
        puts("(your last character was \\n)");

    set_nonblocking(STDIN_FILENO);
    printf("Nonblocking read for ~10s, type something and press enter\n");

    for (int i = 0; i < 10; i++)
    {
        printf("Try %d/10...\n", i + 1);
        n = read(STDIN_FILENO, buf, sizeof(buf) - 1);
        if (n > 0)
        {
            buf[n] = '\0';
            printf("Got %zd bytes: %s", n, buf);
        }
        else if (n == 0)
        {
            printf("EOF\n");
            break;
        }
        else if (errno == EAGAIN || errno == EWOULDBLOCK)
        {
            printf("No data yet (EAGAIN)...\n");
        }
        else
        {
            ERR("read");
        }
        sleep(1);
    }
    return 0;
}
```

Compile and test the program above. In the first, blocking part, both `scanf` and `read` wait for us to enter data and press Enter (by default, the terminal does not send input until it is confirmed with Enter). After switching the descriptor to nonblocking mode, `read` behaves differently: it returns available data without waiting, or reports an error if no data is currently available.

This also shows that an error returned by a function (-1 in this case) does not always mean the program must terminate immediately. With a nonblocking `read`, this is expected: we check `errno` and find that the reason is simply that no data is available (`EAGAIN` or `EWOULDBLOCK`). Only a different error tells us that something went wrong.

Also note the `fcntl` function (`man 3p fcntl`). It lets us inspect and change a descriptor’s properties (flags) after opening it:

```c
int fcntl(int fildes, int cmd, ...);
```

Both `cmd` and the optional third argument can take many values. For file status flags, the commands we need are `F_GETFL` and `F_SETFL`. `F_GETFL` returns the current flags as a bit mask in an `int`. `F_SETFL` takes a mask specifying the flags we want to set. That is why the usual process looks like the `set_nonblocking()` function in the code above: first get the current flags, set the bits we need, and then write them back. Calling `fcntl(fd, F_SETFL, O_NONBLOCK)` instead would be an error, clearing other settable file status flags.

## I/O Multiplexing

As the example above shows, nonblocking I/O is inconvenient when we are waiting for data to arrive. We have to check periodically whether data is available; this is called busy waiting or busy polling. If we write a loop that repeatedly checks for data while waiting, it will fully occupy a processor core. Imagine if every open terminal worked this way: the computer would be unusable.

Alternatively, we can pause between checks, as in the example above with `sleep`. This reduces the load on the system, but increases the program’s response delay. Note that busy waiting is not permitted in the lab unless the task explicitly allows it.

Blocking I/O might seem like the perfect solution: our program is suspended without consuming CPU time, and the system wakes it when data is available and it can continue. But there is a basic problem: we can only wait on one descriptor at a time this way. Until now this was not a problem, because we only knew about stdin (we will soon see some other examples). But imagine having several descriptors like stdin on which we are waiting for data. Nonblocking I/O with busy waiting might seem like the only solution, but it has the significant drawbacks described above.

To solve these problems and enable responsive handling of multiple descriptors, operating systems provide I/O multiplexing. Several functions implement this mechanism: `select` and `poll` (POSIX), and `epoll` (Linux). Below we describe `poll`. You can find a description of `epoll` in the additional material. It is a Linux extension rather than part of POSIX and is highly optimized on that system, but it will not be required in the lab.

### Poll

Let’s start by looking at the signature of `poll` (`man 3p poll`):

```c
int poll(struct pollfd fds[], nfds_t nfds, int timeout);
```

`fds` is an array of structures containing the descriptors we will wait for; we will look at it more closely in a moment. `nfds` is the size of this array. `poll` returns when a descriptor is ready for an operation or when `timeout` milliseconds have elapsed. We can also pass -1 to wait indefinitely.

The `pollfd` structure is described in `man 0p poll.h`. It must define at least the following fields:

- `int fd` - the descriptor to wait for.
- `short events` - a bit mask of the events we want to wait for. The most important for us are `POLLIN`, which waits for data to be ready to read, and `POLLOUT`, which waits for the descriptor to be ready for writing.
- `short revents` - short for returned events: `poll` sets flags in this bit mask to indicate why it returned. These can include the events requested in `events` (`POLLIN` or `POLLOUT`), but also values such as `POLLERR`, `POLLHUP`, and `POLLNVAL`, which indicate an error or a problem with the descriptor. See the manual for details.

To use `poll`, we create an `fds` array and put the descriptors and events we want to wait for in it. For example, to wait for a user to enter data on standard input, we set `.fd` to 0 or `STDIN_FILENO` and `.events` to `POLLIN`. `poll` itself sets `revents`; it is safest to initialize it to zero.

In the following example, we try to read information from `/dev/input/event*` files. On Linux, these provide data from keyboards, mice, and similar input devices. Activating an input device—for example, pressing a key—causes a new `input_event` structure, defined in `linux/input.h`, to become available from the corresponding file. More information about the Linux input subsystem is available at https://www.kernel.org/doc/html/latest/input/input.html.

The header `linux/input-event-codes.h` defines values used in the `input_event` structure—for example, the F key corresponds to the value 33. You do not need to memorize these details; they are not required in the lab. We include them as an interesting example.

```c
#define _POSIX_C_SOURCE 200809L

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <linux/input.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

#define MAX_DEVS 32

int is_event_name(const char *name)
{
    if (strncmp(name, "event", 5) != 0)
        return 0;
    for (int i = 5; name[i] != '\0'; i++)
    {
        if (!isdigit(name[i]))
            return 0;
    }
    return 1;
}

int get_descriptors(struct pollfd fds[MAX_DEVS], char paths[MAX_DEVS][256])
{
    int n = 0;
    DIR *dir = opendir("/dev/input");
    if (!dir)
    {
        ERR("opendir");
    }

    struct dirent *de;
    while ((de = readdir(dir)) != NULL)
    {
        if (!is_event_name(de->d_name))
            continue;
        if (n >= MAX_DEVS)
            break;

        snprintf(paths[n], sizeof(paths[n]), "/dev/input/%s", de->d_name);

        int fd = open(paths[n], O_RDONLY | O_NONBLOCK);
        if (fd < 0)
            ERR("open");

        fds[n].fd = fd;
        fds[n].events = POLLIN;
        fds[n].revents = 0;
        n++;
    }
    closedir(dir);
    return n;
}

int main(void)
{
    struct pollfd fds[MAX_DEVS];
    char paths[MAX_DEVS][256];
    int n = get_descriptors(fds, paths);

    if (n == 0)
    {
        fprintf(stderr, "No readable event devices (check permissions)\n");
        return 1;
    }

    for (int i = 0; i < 30; i++)
    {
        int ret = poll(fds, n, -1);
        if (ret < 0)
            ERR("poll");

        for (int i = 0; i < n; i++)
        {
            if (fds[i].fd < 0)
                continue;

            if (fds[i].revents & (POLLERR | POLLHUP | POLLNVAL))
            {
                close(fds[i].fd);
                fds[i].fd = -1;
                continue;
            }

            if (!(fds[i].revents & POLLIN))
                continue;

            struct input_event ev;
            ssize_t r;
            while ((r = read(fds[i].fd, &ev, sizeof(ev))) == sizeof(ev))
            {
                printf("%s: %ld.%06ld type=%u code=%u value=%d\n", paths[i], (long)ev.input_event_sec,
                       (long)ev.input_event_usec, ev.type, ev.code, ev.value);
            }
        }
    }

    for (int i = 0; i < n; i++)
        if (fds[i].fd >= 0)
            close(fds[i].fd);

    return 0;
}
```

Once the program is running, it prints incoming input events whenever you press a key, move the mouse, and so on.

If the program fails because of insufficient permissions, check the permissions of the files in `/dev/input`. Depending on the system configuration, you may need to belong to the `input` group. In that case, you can add your user to the `input` group (`usermod -aG input <username>`) or grant read permissions (`chmod a+r /dev/input/*`). Either way, this requires administrator privileges (`sudo` or `su`). Access to input devices can expose keystrokes, including passwords, so only grant it to trusted users. You can also run the program with those privileges using `sudo`.

If you still cannot run the program (for example, because you are using a university computer without administrator privileges), don’t worry; keep reading. Analyze how the program works and try modifying it to work with the descriptors described below, which should not require special configuration.

> **Question:** When does the program finish?
>
> **Answer:** The program finishes after `poll` has returned 30 times. This is not the same as receiving 30 events. In one iteration we can read events from several devices, and each device may have several events queued.

> **Question:** Why did we open the files in nonblocking mode? Would the program work with descriptors in blocking mode?
>
> **Answer:** Be careful when combining blocking I/O with multiplexing. Notice that `poll` only tells us that some data is available; we do not know how much. With a nonblocking descriptor, we can simply keep reading until there is no more data, which is what we do. With blocking descriptors, the program would wait in the `read` loop once it had consumed the available events.
>
> We could remove the loop and read only one message at a time. If several were available, `poll` would return immediately and we could read the next one. However, we must be careful: here we know the data has the size of an `input_event` structure. Without that guarantee, we might have to read one byte at a time. Nonblocking I/O is much better suited to this case: blocking I/O has no advantages here and risks blocking the program.

> **Question:** Can we use `poll` to read ordinary files?
>
> **Answer:** We can, but there is not much point. Ordinary files are always ready to read, so `poll` returns immediately.

What other kinds of files can we usefully poll? Among those encountered so far (in the Operating Systems course and “UNIX System Basics”) are character devices, including terminals (`/dev/tty`, as well as our programs’ standard input and output), the `/dev/input/*` devices shown above, and many other files in `/dev`. Other examples include pipes and FIFOs, network sockets, and many other descriptors returned by system functions (`timerfd`, `signalfd`, `inotify`, etc.).

### Named Pipes in Brief

Named pipes, also known as FIFOs (`man 7 fifo`), are a special type of file through which programs can exchange data. They will be covered in detail in Operating Systems 2 when discussing IPC (inter-process communication). We will show the basics here because a FIFO is a good, simple example of a file that can be used with `poll`.

The easiest way to create a named pipe from the command line is `mkfifo <name>` (`man 1 mkfifo`). This creates a FIFO file with the specified name. Programs can write data to and read data from it, but the data is not retained: reading data from a FIFO also removes it. The easiest way to try pipes is from the command line. In one terminal, create a FIFO and start reading from it:

```
mkfifo my_fifo
cat my_fifo
```

`cat` will wait until data appears in the FIFO. In a second terminal, enter:

```
echo "message" > my_fifo
```

After this command runs, `cat` in the first terminal should print our message. We can then remove the pipe using the ordinary `rm` command.

In a C program, we can create a FIFO using `mkfifo` (`man 3p mkfifo`):

```c
int mkfifo(const char *path, mode_t mode);
```

`path` is the path and `mode` specifies the permissions, just as with `mkdir`.

Once the FIFO is created, we use it much like an ordinary file: open it with `open`, read and write with `read` and `write`, and finally close it with `close`. We can also remove it with `unlink`. Naturally, we can open it in blocking or nonblocking mode and use `poll` for multiplexing.

### Timerfd (Additional Material)

A simple and very useful mechanism for testing `poll` is `timerfd`. It is a Linux extension (not part of POSIX), so it will not be required in the lab. However, it is useful and interesting, so the rest of this subsection is worth reading.

`timerfd` lets us create timers that we then read through a descriptor. The full description is in `man 2 timerfd`.

To create a new timer, use:

```c
int timerfd_create(int clockid, int flags);
```

`clockid` specifies the system clock to use. The simplest choice is `CLOCK_REALTIME`, but there are other options described in the manual. Of the flags that can be set, `TFD_NONBLOCK` is particularly relevant to us.

Once the timer has been created, set it using:

```c
int timerfd_settime(int fd, int flags, const struct itimerspec *new_value,
                         struct itimerspec *_Nullable old_value);
```

Pass the descriptor obtained from `timerfd_create`. The `new_value` parameter specifies the timer settings. The structure has two fields (`man 3type itimerspec`): `it_value` sets the time until the first expiration, and `it_interval` can be used to set periodic expirations. Both fields are of type `timespec` (`man 3type timespec`), meaning they specify seconds and nanoseconds. Many useful functions use `timespec`, so it is worth getting familiar with it. The `old_value` parameter is optional and can be set to `NULL`; see the manual for more information.

```c
#define _POSIX_C_SOURCE 200809L

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/timerfd.h>
#include <unistd.h>

#define ERR(source) (perror(source), fprintf(stderr, "%s:%d\n", __FILE__, __LINE__), exit(EXIT_FAILURE))

int main(void)
{
    struct itimerspec new_value;
    memset(&new_value, 0, sizeof(new_value));
    new_value.it_value.tv_sec = 2;

    int fd = timerfd_create(CLOCK_REALTIME, 0);
    if (fd == -1)
        ERR("timerfd_create");

    printf("Preparing timer for waiting for 2 seconds\n");
    if (timerfd_settime(fd, 0, &new_value, NULL) == -1)
        ERR("timerfd_settime");

    uint64_t val = 0;
    if (read(fd, &val, sizeof(uint64_t)) < 0)
        ERR("read");
    printf("2 seconds passed, got %lu from timer, exiting now\n", val);

    return 0;
}
```

The behavior of the program above should be clear. To confirm that the timer works correctly, you can run the program with the `time` command, for example `time ./l2-5`.

Notice that we did not set the timer to nonblocking mode in this example. The goal was to demonstrate this feature as simply as possible, so we use a single `read`. As an exercise, try modifying the previous `poll` program so that it ends after a certain amount of time (or perhaps after a certain period of inactivity; try a few things!).

### Epoll (Additional Material)

`poll` is easy to use and solves most of our problems. But what if there are a great many descriptors? When using `poll`, we still have to iterate over all of them, which limits performance. On Linux, a possible solution is `epoll`, described in separate additional material. You are encouraged to read it, although it will not be required in the lab.

## Example tasks

Do the example tasks. During the laboratory you will have more time and the starting code. However, if you finish the following tasks in the recommended time, you will know you’re well prepared for the laboratory.
