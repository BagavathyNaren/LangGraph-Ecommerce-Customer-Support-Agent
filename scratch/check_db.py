import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))
load_dotenv()

from tools.real_tools import get_customer_orders


def main():
    res = get_customer_orders("naren fresh guest 2659")
    print("get_customer_orders returned:")
    print(res)


if __name__ == "__main__":
    main()
