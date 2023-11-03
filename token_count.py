import tiktoken
import sys

# count number of tokens for OpenAI's models
def num_tokens_from_string(string: str, encoding_name = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


if __name__ == "__main__":
    filename  = sys.argv[1]
    with open(filename, "r") as f:
        s = f.read()
        token_count = num_tokens_from_string(s)
        print(f"Token count is {token_count}")