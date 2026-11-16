#!/bin/bash

# Contents:
# 1. CONDITIONAL COMMAND EXECUTION


echo
echo "*** CONDITIONAL COMMAND EXECUTION ***"
echo


# We can run a command conditionally: on succes (&&) or on failure (||) 
# of the preceding one
# We ignore error messages by redirecting stderr to /dev/null
kill 1 2>/dev/null || echo "Can't kill the \`init' process"

echo

# We can use the `if' statement
if true
then
	echo "What is the truth?"
fi

# `if' can fit a single line if semicolons are used
# `!' is a logical negation operator
if ! false; then echo "False is not truth"; fi

# 0 is `true', other values are `false'
# Most commands return 0 on success
# `!' is a logical negation operator
if ! kill 1 2>/dev/null
then 
	echo "Regular users can't kill \`init' -- that's the truth"
fi

echo

# Were there any parameters specified -- is `$1' empty?
# (there must be space after `[' and before `]')
if [ -z $1 ] 
then 
	echo "No program parameters were specified"
else
	echo "The first parameter is $1"
fi

# The more `[' the better?
# (there must be space after `[[' and before `]]')
if [[ -z $1 ]]
then 
	echo "No program parameters were specified"
else
	echo "The first parameter is $1"
fi

echo

# `[[' is a bash built-in while `[' is an external command
# `man bash' `/CONDITIONAL EXPRESSIONS' lists possible operators for `[['
# `[' is the same as `test'. Run `man test' for help on `['
# `[' and `[[' differ is some ways, for example we use different logical `and'
A=10; B=2
if [ $A -eq 10 -a $B -eq 2 ]      ; then echo "A=10 B=2"; fi
if [[ ($A -eq 10) && ($B -eq 2) ]]; then echo "A=10 B=2"; fi

# Use `-lt',`-gt' and `-eq' for numerical comparison
# `<',`>' and `=' compare strings lexicographically!
# Note that since `[' is a command we must escape the `<' or it is considered 
# a redirection operator otherwise
if [ $A \< $B ] ; then echo "$A < $B"; fi
if [[ $A < $B ]]; then echo "$A < $B"; fi

# Some programmers prefer simple syntax whenever possible
[ $A \< $B ]  && echo "$A < $B"
[[ $A < $B ]] && echo "$A < $B"

echo

# `$?' stores the return value of the most recent command
echo "cd /non-existing-directory"
cd /non-existing-directory 2>/dev/null
echo "return value: $?"
