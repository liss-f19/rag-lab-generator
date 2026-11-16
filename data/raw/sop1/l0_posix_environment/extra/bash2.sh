#!/bin/bash

# Contents:
# 1. INTERPRETING USER'S CHOICE
# 2. WHILE LOOP
# 3. READING SCRIPT OPTIONS


echo
echo "*** INTERPRETING USER'S CHOICE ***"
echo


# Double quotes don't protect ` so we have to escape it
echo "Enter: \`yes' or \`no'"

# `man read' if in doubt but... is it really necessary?
read CHOICE

# Remember to place double semicolon after each clause
# The `*' is a wildcard (`anything'); never place it before other patterns!
case $CHOICE in
	yes) echo "your choice: yes";;
	no) echo "your choice: no";;
	*) echo "other choice";;
esac


echo
echo "*** WHILE LOOP ***"
echo


echo "Quit gvim if it's running, please"

# ps + grep = pgrep 
# We'll redirect stdout and stderr of this command to /dev/null because 
# we don't need its output; we are only interested in its exit status:
# `pgrep gvim' returns 0 if gvim is running and other value otherwise
# Remember: 0 is equal to `true' and other values mean `false'!
while pgrep gvim 1>/dev/null 2>&1
do
	echo "gvim still running"
	echo "Taking a 5 sec. nap"
	sleep 5
done

echo "gvim not running anymore"

# You can put whole `while' on a single line if you use semicolons:
# `while somevalue; do something; done'

# The other command: `until' works analogously to `while'


echo
echo "*** READING SCRIPT OPTIONS ***"
echo


# Let's assume that our script accepts two options: `-a' and `-b'
# It can be invoked with `-a', `-b', `-ab' and `-ba' options
# We can examine $1, $2 etc. and analyze strings...
# ... or we can make use of the `getopts' command in conjunction with 
# `while' and `case'
while getopts "ab" option 2>/dev/null
do
	case $option in
		a) echo "option \`-a' active" ;;
		b) echo "option \`-b' active" ;;
		?) echo "unrecognized option"; exit 1 ;;
	esac
done

# For a key-value option: `-a value' we'll use:
#    while getopts "a:b" option 2>/dev/null
#    ...
#        a) echo "option \`-a' is assigned the value: $OPTARG";;
#    ...
