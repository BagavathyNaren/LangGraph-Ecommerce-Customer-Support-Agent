try:
    from googlesearch import search

    print("googlesearch-python is installed!")
    results = list(search("Samsung S24 Ultra", num_results=3))
    print("Results:")
    for r in results:
        print("-", r)
except Exception as e:
    print("Error:", e)
