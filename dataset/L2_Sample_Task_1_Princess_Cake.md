# L2 Sample Task 1: Princess Joanna’s Cake

*Topic: L2 — Filesystem (sample task)*


## Description

Princess Joanna’s birthday is approaching in the Shining Gem castle. The court cooks want to bake the legendary Cake, but only the old grannies know the recipe. They gossip over tea in the castle towers and dictate the steps to the kitchen through named pipes. They talk with their mouths full, so the steps arrive in pieces, and when they get carried away gossiping, they mix up the step numbers. On top of that, Joanna visits every granny and spills tea and crumbles cookies over their notes, so the word raspberries is sometimes written as `raw~berries`.

Write a program `sop-cake recipe tower1 [tower2 ... tower5]`, where `recipe` is the path to the recipe file and `tower1`... are paths to the named pipes through which the grannies dictate.

The recipe is a 2048-byte file: 32 lines of 64 bytes each (63 characters padded with spaces + `\n`), line NN is step number NN. A granny sends messages `NN:content\n` (ASCII, at most 127 bytes without `\n`). A message is valid if there is only a number from 0 to 31 before the colon.

Grannies are created with the `granny.sh` script. The command `./granny.sh <tower> <number_of_steps>` creates the named pipe `<tower>`, waits until someone opens it for reading, then dictates the steps, printing them in its terminal, and finally removes the pipe. Start each granny in a separate terminal before you start the program:

```
terminal 1:  $ ./granny.sh tower1 8
terminal 2:  $ ./granny.sh tower2 8
terminal 3:  $ ./sop-cake recipe.txt tower1 tower2
```

Files and descriptors must be handled only with low-level functions. Busy waiting is forbidden.

## Stages

### Stage 1

If the recipe file does not exist, the program creates it with the `write` function as 32 empty lines (each line is 63 spaces + `\n`). If it exists, the program opens it and checks with `lseek` whether it is exactly 2048 bytes long – if the size is different, it prints “This book is not a recipe!” on stderr and exits.

Then the program opens the `tower1` pipe for reading. If such a file does not exist or is not a named pipe, the program prints “There is no granny in X” on stderr, where X is the given path, and exits. Finally, it reads data from the pipe until EOF and prints it unchanged on stdout.

Hint: a named pipe is opened with the `open` function just like a regular file – see the tutorial. You can check the file type with the `stat` or `fstat` function and the `S_ISFIFO` macro (`man 7 inode`). Open the recipe file with the `O_RDWR` flag from the start – `mmap` in stage 4 will need it.

To show:

```
terminal 1:  $ ./granny.sh tower1 8
terminal 2:  $ ./sop-cake recipe.txt tower1
terminal 2:  $ cat recipe.txt                     # the created file
terminal 2:  $ ./sop-cake recipe.txt recipe.txt   # no granny
terminal 2:  $ ./sop-cake granny.sh tower1        # wrong recipe
```

### Stage 2

Instead of printing the data from the pipe, the program splits it into messages terminated with `\n` – one message may arrive in several `read` calls. The program writes a valid step in the `NN:content` format into line NN of the recipe file. Only content goes into the file, without the `NN:` prefix, truncated to 63 characters and padded with spaces. Then the program prints “Step NN saved” on stdout, where NN always has two digits (e.g. 07). Invalid messages are skipped and the program prints “Granny got carried away: ” on stderr.

To show:

```
terminal 1:  $ ./granny.sh tower1 8
terminal 2:  $ ./sop-cake recipe.txt tower1
terminal 2:  $ cat recipe.txt                     # the saved steps
```

### Stage 3

The program opens all given pipes (`tower1` … `tower5`) and waits for data from all of them at once using the `poll` function. When it detects the end of file on a pipe, the program closes its descriptor, prints “Granny from X finished dictating” on stdout (X is the path of the pipe) and removes it from the set monitored by `poll`. If no data arrives on any pipe for 3 seconds, the program prints “Grannies are pouring more tea…” on stdout and keeps waiting.

Hint: pieces of messages from different pipes may arrive alternately, so each pipe needs its own buffer for the unfinished message.

To show:

```
terminal 1:  $ ./granny.sh tower1 8
terminal 2:  $ ./granny.sh tower2 8
terminal 3:  $ ./granny.sh tower3 8
terminal 4:  $ ./sop-cake recipe.txt tower1 tower2 tower3
```

The message about pouring tea is easiest to see when running only one granny.

### Stage 4

When all pipes are closed, the program maps the recipe file into memory with the `mmap` function. In memory, it replaces every occurrence of `raw~berries` with `raspberries`. Then it prints on stdout:

- “Princess Joanna’s stains cleaned: N”, where N is the number of replaced occurrences,
- every non-empty step (a line that does not consist of spaces only) in the `NN: content` format, in the order of step numbers, where NN always has two digits and content is printed without the padding spaces at the end of the line,
- “Missing K steps, the cake will collapse!”, where K is the number of empty lines, or “Cake ready!” if no line is empty.

To show:

```
terminal 1:  $ ./granny.sh tower1 8
terminal 2:  $ ./granny.sh tower2 8
terminal 3:  $ ./granny.sh tower3 8
terminal 4:  $ ./sop-cake recipe.txt tower1 tower2 tower3
terminal 4:  $ grep -c '~' recipe.txt             # should print 0
```

Remember to release all resources at the end by calling `munmap` and closing all open descriptors!

## granny.sh

Code for the `granny.sh` file:

```bash
#!/bin/bash

if [ $# -ne 2 ]; then
    echo "Usage: $0 <fifo> <steps_count>" >&2
    exit 1
fi

# princess Joanna spilled tea and crumbled cookies over the granny's notes - raspberries became raw~berries
steps=(
    "Preheat the oven to 180 degrees"
    "Line three cake tins with baking paper"
    "Separate the yolks from the whites of twelve eggs"
    "Beat the egg whites stiff with a pinch of salt"
    "Gradually add sugar while still beating"
    "Add the yolks one at a time, mixing constantly"
    "Sift wheat flour together with potato starch"
    "Gently fold in the flour with a spatula"
    "Pour the batter into the tins and level the tops"
    "Bake for 35 minutes until a skewer comes out dry"
    "Cool the sponges and slice each one in half"
    "Boil water with lemon juice, sugar and a few raw~berries"
    "Cream the butter until light and fluffy"
    "Mash half of the raw~berries, keep the other raw~berries whole"
    "Fold in mascarpone and seeds from a vanilla pod"
    "Divide the cream into three equal parts"
    "Add melted dark chocolate to the first part"
    "Add pureed raw~berries to the second part"
    "Leave the third part white, princess Joanna loves it the most"
    "Soak the first sponge layer with syrup"
    "Spread it with the chocolate cream"
    "Cover with the next sponge layer and soak it"
    "Spread the raspberry cream and lay fresh raw~berries on top"
    "Repeat the layers until all the sponges are used"
    "Chill the cake overnight in the castle cellar"
    "Cover the sides with white cream and press in raw~berries"
    "Melt sugar in a saucepan into golden caramel"
    "Shape small crowns out of the caramel and raw~berries"
    "Sprinkle the top with edible gold and crushed raw~berries"
    "Place the crowns on top, surrounded by raw~berries"
    "Put three candles in the cake"
    "Serve with tea, the grannies get the biggest slices"
)
fifo=$1
n=$2

if ! [[ $n =~ ^[0-9]+$ ]]; then
    echo "steps_count must be a non-negative number" >&2
    exit 1
fi

if [ -e "$fifo" ] || [ -p "$fifo" ]; then
    echo "FIFO $fifo already exists. Another granny may be using it." >&2
    exit 1
fi

if ! mkfifo "$fifo"; then
    echo "Cannot create named pipe $fifo" >&2
    exit 1
fi

# remove the pipe if script ends
trap 'rm -f "$fifo"' EXIT
trap 'exit 130' INT TERM HUP QUIT
# ignore SIGPIPE
trap '' PIPE

echo "Granny from $fifo is waiting for the kitchen to listen..."

exec {fd}>"$fifo"

echo "Granny from $fifo starts dictating"

for ((i = 0; i < n; i++)); do
    step=$((RANDOM % ${#steps[@]}))
    text=${steps[$step]}

    # the granny got carried away gossiping and mixed up the step number
    num=$step
    if ((RANDOM % 8 == 0)); then
        num=$((RANDOM % 68 + 32))
    fi

    msg=$(printf '%02d:%s' "$num" "$text")
    echo "$msg"

    if ((RANDOM % 3 == 0)); then
        # the granny talks with her mouth full - the message arrives in two pieces
        cut=$((RANDOM % ${#msg}))
        printf '%s' "${msg:0:cut}" >&"$fd" || break
        sleep $((RANDOM % 4 + 1))
        printf '%s\n' "${msg:cut}" >&"$fd" || break
    else
        printf '%s\n' "$msg" >&"$fd" || break
    fi

    if ((RANDOM % 6 == 0)); then
        echo "(gossip over tea)"
        sleep 4
    else
        sleep 0.$((RANDOM % 9 + 1))
    fi
done

exec {fd}>&-
if ((i < n)); then
    echo "The kitchen stopped listening, granny from $fifo goes back to her tea" >&2
    exit 1
fi
echo "Granny from $fifo has finished dictating"
```
