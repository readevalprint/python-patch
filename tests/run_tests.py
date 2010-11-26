"""
TestSuite

Files/directories that comprise one test all have the same name, but a different extensions:
*.patch
*.from
*.to

*.doctest   - self contained doctest patch

TODO: recheck input/output sources

"""

import os
import sys
import re
import shutil
import unittest
import copy
from os import listdir
from os.path import abspath, dirname, exists, join, isdir
from tempfile import mkdtemp

verbose = False
if "-v" in sys.argv or "--verbose" in sys.argv:
  verbose = True


#: full path for directory with tests
tests_dir = dirname(abspath(__file__))


# import patch.py from parent directory
save_path = sys.path
sys.path.insert(0, dirname(tests_dir))
import patch
sys.path = save_path


# ----------------------------------------------------------------------------
class TestPatchFiles(unittest.TestCase):
  """
  unittest hack - test* methods are generated by add_test_methods() function
  below dynamicallt using information about *.patch files from tests directory

  """
  def _assert_files_equal(self, file1, file2):
      f1 = f2 = None
      try:
        f1 = open(file1, "rb")
        f2 = open(file2, "rb")
        for line in f1:
          self.assertEqual(line, f2.readline())

      finally:
        if f2:
          f2.close()
        if f1:
          f1.close()
  
  def _assert_dirs_equal(self, dir1, dir2, ignore=[]):
      """ compare dir1 with reference dir2
          .svn dirs are ignored

      """
      # recursion here
      e2list = listdir(dir2)
      for e1 in listdir(dir1):
        if e1 == ".svn":
          continue
        e1path = join(dir1, e1)
        e2path = join(dir2, e1)
        self.assert_(exists(e1path))
        self.assert_(exists(e2path), "%s does not exist" % e2path)
        self.assert_(isdir(e1path) == isdir(e2path))
        if not isdir(e1path):
          self._assert_files_equal(e1path, e2path)
        else:
          self._assert_dirs_equal(e1path, e2path)
        e2list.remove(e1)
      for e2 in e2list:
        if e2 == ".svn" or e2 in ignore:
          continue
        self.fail("extra file or directory: %s" % e2)

  
  def _run_test(self, testname):
      """
      boilerplate for running *.patch file tests
      """

      # 1. create temp test directory
      # 2. copy files
      # 3. execute file-based patch 
      # 4. compare results
      # 5. cleanup on success

      tmpdir = mkdtemp(prefix="%s."%testname)

      patch_file = join(tmpdir, "%s.patch" % testname)
      shutil.copy(join(tests_dir, "%s.patch" % testname), patch_file)
      
      from_src = join(tests_dir, "%s.from" % testname)
      from_tgt = join(tmpdir, "%s.from" % testname)

      if not isdir(from_src):
        shutil.copy(from_src, from_tgt)
      else:
        for e in listdir(from_src):
          if e == ".svn":
            continue
          epath = join(from_src, e)
          if not isdir(epath):
            shutil.copy(epath, join(tmpdir, e))
          else:
            shutil.copytree(epath, join(tmpdir, e))


      # 3.
      # test utility as a whole
      patch_tool = join(dirname(tests_dir), "patch.py")
      save_cwd = os.getcwdu()
      os.chdir(tmpdir)
      if verbose:
        ret = os.system('%s %s "%s"' % (sys.executable, patch_tool, patch_file))
      else:
        ret = os.system('%s %s -q "%s"' % (sys.executable, patch_tool, patch_file))
      assert ret == 0, "Error %d running test %s" % (ret, testname)
      os.chdir(save_cwd)


      # 4.
      # compare results
      if not isdir(from_src):
        self._assert_files_equal(join(tests_dir, "%s.to" % testname), from_tgt)
      else:
        # need recursive compare
        self._assert_dirs_equal(join(tests_dir, "%s.to" % testname), tmpdir, "%s.patch" % testname)

        

      shutil.rmtree(tmpdir)
      return 0


def add_test_methods(cls):
    """
    hack to generate test* methods in target class - one
    for each *.patch file in tests directory
    """

    # list testcases - every test starts with number
    # and add them as test* methods
    testptn = re.compile(r"^(?P<name>\d{2,}.+)\.(?P<ext>[^\.]+)")
    testset = sorted( set([testptn.match(e).group('name') for e in listdir(tests_dir) if testptn.match(e)]) )

    for filename in testset:
      methname = filename.replace(" ", "_")
      def create_closure():
        name = filename
        return lambda self: self._run_test(name)
      setattr(cls, "test%s" % methname, create_closure())
      if verbose:
        print "added test method %s to %s" % (methname, cls)
add_test_methods(TestPatchFiles)

# ----------------------------------------------------------------------------

class TestCheckPatched(unittest.TestCase):
    def setUp(self):
        self.save_cwd = os.getcwdu()
        os.chdir(tests_dir)

    def tearDown(self):
        os.chdir(self.save_cwd)

    def test_patched_multiline(self):
        pto = patch.fromfile(join(tests_dir, "01uni_multi.patch"))
        os.chdir(join(tests_dir, "01uni_multi.to"))
        self.assert_(pto.can_patch("updatedlg.cpp"))

    def test_can_patch_single_source(self):
        pto2 = patch.fromfile(join(tests_dir, "02uni_newline.patch"))
        self.assert_(pto2.can_patch("02uni_newline.from"))

    def test_can_patch_fails_on_target_file(self):
        pto3 = patch.fromfile(join(tests_dir, "03trail_fname.patch"))
        self.assertEqual(None, pto3.can_patch("03trail_fname.to"))
        self.assertEqual(None, pto3.can_patch("not_in_source.also"))
   
    def test_multiline_false_on_other_file(self):
        pto = patch.fromfile(join(tests_dir, "01uni_multi.patch"))
        os.chdir(join(tests_dir, "01uni_multi.from"))
        self.assertFalse(pto.can_patch("updatedlg.cpp"))

    def test_single_false_on_other_file(self):
        pto3 = patch.fromfile(join(tests_dir, "03trail_fname.patch"))
        self.assertFalse(pto3.can_patch("03trail_fname.from"))

    def test_can_patch_fails_even_if_file_in_targets_can_be_patched(self):
        pto2 = patch.fromfile(join(tests_dir, "04can_patch.patch"))
        self.assert_(not pto2.can_patch("04can_patch.to"))

# ----------------------------------------------------------------------------

class TestPatchParse(unittest.TestCase):
    def test_fromstring(self):
        try:
          f = open(join(tests_dir, "01uni_multi.patch"), "rb")
          readstr = f.read()
        finally:
          f.close()
        pto = patch.fromstring(readstr)
        self.assertEqual(len(pto.source), 5)

# ----------------------------------------------------------------------------


if __name__ == '__main__':
    unittest.main()
