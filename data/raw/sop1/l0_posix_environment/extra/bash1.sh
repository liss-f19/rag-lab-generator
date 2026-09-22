#!/bin/bash

# Contents:
# 1. SCRIPT PARAMETERS
# 2. DISPLAYING MULTI-LINE TEXT
# 3. FUNCTIONS AND THEIR PARAMETERS

# Don't change the first line! 
# It specifies the interpreter to use for this file if its run as a program.
# Additionally set the `x' permission on this script: `chmod +x bash1.sh' 
# and instead of `bash bash1.sh' you can run it simply as a program: 
# `bash1.sh' (if in $PATH) or `./bash1.sh' otherwise


# Print an empty line
echo
echo "*** SCRIPT PARAMETERS ***"
echo


# Display script name
# What is the output if you run it: './bash1.sh' ?
# What is the output if you run it: 'bash bash1.sh' ?
echo "You are running: $0"

# Display script parameters
# Don't worry if none were specified. Uninitialized variables are just ''
echo "Script parameters are: $1 $2 $3"


echo
echo "*** DISPLAYING MULTI-LINE TEXT ***"
echo


# Simply way of displaying multi-line text...
echo "Multi-line text:"
echo "----------------"

# ... and the smart way
cat << SOMETAG
Litwo! Ojczyzno moja! ty jestes jak zdrowie.
Ile cie trzeba cenic, ten tylko sie dowie,
Kto cie stracil. Dzis pieknosc twa w calej ozdobie
Widze i opisuje, bo tesknie po tobie. 
SOMETAG


echo
echo "*** FUNCTIONS AND THEIR PARAMETERS ***"
echo


# We define a function...
# (there must be space after `{' and before `}'; 
# if there is a command in the same line as `}' it must end with semi-colon)
fun() { echo "Calling a function"; }

# ...and we call it
fun

# Function with parameters...
fun2() {
	echo "Other function with parameters: $1 $2 $3"
	}

# ...can be used as any other program
fun2 one two three

# Read in the manual `man bash' about the `shift' built-in
