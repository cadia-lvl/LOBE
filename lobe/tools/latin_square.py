def balanced_latin_squares(n):
    """
    courtesy of https://medium.com/@graycoding/balanced-latin-squares-in-python-2c3aa6ec95b9

    For a given number, this function will give all the rows in a ~balanced~ latin square.

    Usage: The outputs of this functions should be used to define the different variations of a MOS test
        in order to balance the test, both in terms of different voices heard by each listener, 
        and in terms of the order in which they are heard.
    Input: positive integer n
    Output: Array of arrays of list indices of length n
    """
    l = [[((j//2+1 if j%2 else n-j//2) + i) % n for j in range(n)] for i in range(n)]
    if n % 2:  # Repeat reversed for odd n
        l += [seq[::-1] for seq in l]
    return l