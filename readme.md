# furigana server

Store Japanese words in `tsv` file.

As I came across Japanese words, I wanted to note down those words and to be able to look it up later. A simple way is to store them in text file (a `tsv` file to be able to store relevant information with that word). However, I had to indent every columns and the whole `tsv` file was too large to focus on the information that I want to get.

## Note

- There is a lot of global variables and they are not all defined at the top.
- I use global variables because we don't explicit create the `HTTPRequestHandler`. The class name is passed to `HTTPServer`'s `__init__` method so I do not know for sure how parameters are passed and not like the idea of passing arbitratry array of arguments that I don't have control of. And they are created for every requests so that is not a good object to store the application state.
