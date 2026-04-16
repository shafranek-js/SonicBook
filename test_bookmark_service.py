import unittest
from bookmark_service import _normalize_book_name

class TestBookmarkService(unittest.TestCase):
    def test_normalize_book_name_standard(self):
        self.assertEqual(_normalize_book_name("The Great Gatsby"), "the great gatsby")

    def test_normalize_book_name_with_extension(self):
        self.assertEqual(_normalize_book_name("The Great Gatsby.mp3"), "the great gatsby")
        self.assertEqual(_normalize_book_name("book_name.m4b"), "book_name")

    def test_normalize_book_name_special_chars(self):
        self.assertEqual(_normalize_book_name("Book-Name! @With# Special$ Characters%"), "book name with special characters")
        self.assertEqual(_normalize_book_name("Book_Name_With_Underscores"), "book_name_with_underscores") # \w includes underscores

    def test_normalize_book_name_unicode(self):
        self.assertEqual(_normalize_book_name("Толстой - Война и мир.mp3"), "толстой война и мир")
        self.assertEqual(_normalize_book_name("L'Étranger"), "l étranger")

    def test_normalize_book_name_extra_spaces(self):
        self.assertEqual(_normalize_book_name("  Book   with    spaces  "), "book with spaces")

    def test_normalize_book_name_empty(self):
        self.assertEqual(_normalize_book_name(""), "")
        self.assertEqual(_normalize_book_name(None), "")

    def test_normalize_book_name_path(self):
        self.assertEqual(_normalize_book_name("/path/to/some/Book Name.mp3"), "book name")

if __name__ == '__main__':
    unittest.main()
