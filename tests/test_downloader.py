import unittest
from sonir.downloader import AudioDownloader

class TestDownloader(unittest.TestCase):
    def test_is_url(self):
        self.assertTrue(AudioDownloader.is_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(AudioDownloader.is_url("http://soundcloud.com/artist/song"))
        self.assertTrue(AudioDownloader.is_url("https://youtu.be/dQw4w9WgXcQ"))
        
        self.assertFalse(AudioDownloader.is_url("C:\\Music\\song.mp3"))
        self.assertFalse(AudioDownloader.is_url("/home/user/music/song.wav"))
        self.assertFalse(AudioDownloader.is_url("song.mp3"))

if __name__ == '__main__':
    unittest.main()

