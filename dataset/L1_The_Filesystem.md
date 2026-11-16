# L1: The Filesystem

*Topic: L1 — Filesystem*


A secret agent with the pseudonym `ACK` has sent you a secret message in a cipher of his own making. He has managed to get into your repository and create a folder structure with files containing seemingly random strings of letters. We have figured out what the code is, and now it's your task to implement a program that will allow us to read the message.

Every file contains a set of characters. The message contained in that file is that unique set of characters, sorted by the number of appearances first, ASCII value second (in case the appearance number is the same).

Example (quotes `""` added for clarity `./data/cypher3/pseudonym`):

```
" |  AA ::: CCCC ----- KKKKKK "
```

This file's message is: `"|A:C-K "` (without quotes), the agent's signature.

This mode of communication turns out to be very inefficient in terms of file size. We have devised an intermediate cipher that still ensures the message is hidden and requires much less space. We're going to use that cipher to communicate with our allies in the future, but also need a way to convert agent `ACK`'s messages to our code. The file in our intermediate cipher is structured as follows:

- **a)** The first four bytes contain the binary representation of an integer *N*. It represents how many unique characters are in the message.
- **b)** The next *N* bytes contain the unique characters themselves.
- **c)** The next 4 · *N* bytes contain the (integer) binary representations of the numbers of character appearances in the order they appear in section *b)*.

## Note

- There are several functions defined in the starting code. Don't change their signatures. Fill them in as you're completing the tasks. You can define additional functions.
- The function `secret_decoder_comparison_function` is already implemented for you. Do not change it if you want to see the finished message.
- There is also a global variable `int histogram[256]`. Do not define additional global variables.
- Free all unused resources accordingly. Check all system functions for errors (it's sufficient to display information about the error and close the program).

## Stages

### Stage 1 (6 p.)

The program should be executed with exactly 2 arguments. The first one specifying the command, second - a path to the input. The program does something different for each of the 3 commands. If the command doesn't appear on the list, print the error (describing what the problem is) and exit.

- `analyze` - if the input is a regular file or a link pointing to a regular file, the program executes the `analyze_file` function; otherwise report the error and exit.
- `decode` - if the input is a regular file (not a link!), the program executes the `decode_message` function; otherwise report the error and exit.
- `batch` - if the input is a directory (not a link!), the program executes the `batch_decode` function; otherwise report the error and exit.

### Stage 2 (7 p.)

Implement the `analyze_file` function. Count the characters in the file using the `histogram` variable. For example, `histogram[(int)'a']` should equal the number of times the character `'a'` occurs in the file. Display that data in a table on the console. Only display the characters that appear in the file. The output should be the same as the command `"cat data/surname | fold -w 1 | sort | uniq -c"`

Example (`./data/cypher3/pseudonym`):

```
8
5 -
3 :
2 A
4 C
6 K
1 |
```

Convert the message to the intermediate cipher and save it under `./output/analysis`. The intermediate cipher is described in the first section of this document.

### Stage 3 (5 p.)

Implement the `decode_message` function. Read the character counts from a file in the intermediate cipher into the `histogram` variable using `readv`. Implement `qsort_comparison_function` and sort the unique characters using `qsort` (`man 3p qsort`). Display the message on the console. Find out the agent's surname by analyzing and decoding the `./data/surname` file. Create the `./output` directory if it doesn't exist.

### Stage 4 (6 p.)

Implement the `batch_decode` function. Traverse the target directory recursively, analyze and decode all of the files. Don't implement the recursive walk yourself, use `nftw`. Save each result into a file of the same name directly in the `./output` directory (create it if it doesn't exist). Follow links, but don't let your program fail on dangling ones.

After you've translated the whole message, use `"cat ./output/*"` to see what the agent was trying to tell you.
