"""
Author: Joon Sung Park (joonspk@stanford.edu)

File: spatial_memory.py
Description: Defines the MemoryTree class that serves as the agents' spatial
memory that aids in grounding their behavior in the game world. 
"""
import json
import sys
sys.path.append('../../')

from utils import *
from global_methods import *

class MemoryTree: 
  def __init__(self, f_saved): 
    self.tree = {}
    if check_if_file_exists(f_saved): 
      with open(f_saved, encoding="utf-8") as _f:
        self.tree = json.load(_f)


  def print_tree(self): 
    def _print_tree(tree, depth):
      dash = " >" * depth
      if type(tree) == type(list()): 
        if tree:
          print (dash, tree)
        return 

      for key, val in tree.items(): 
        if key: 
          print (dash, key)
        _print_tree(val, depth+1)
    
    _print_tree(self.tree, 0)
    

  def save(self, out_json):
    with open(out_json, "w", encoding="utf-8") as outfile:
      json.dump(self.tree, outfile)



  def get_str_accessible_sectors(self, curr_world): 
    """
    Returns a summary string of all the arenas that the persona can access 
    within the current sector. 

    Note that there are places a given persona cannot enter. This information
    is provided in the persona sheet. We account for this in this function. 

    INPUT
      None
    OUTPUT 
      A summary string of all the arenas that the persona can access. 
    EXAMPLE STR OUTPUT
      "bedroom, kitchen, dining room, office, bathroom"
    """
    try:
      x = ", ".join(list(self.tree[curr_world].keys()))
      return x
    except Exception:
      # 如果当前世界在记忆树中不存在，返回空字符串以避免上层崩溃
      return ""


  def get_str_accessible_sector_arenas(self, sector): 
    """
    Returns a summary string of all the arenas that the persona can access 
    within the current sector. 

    Note that there are places a given persona cannot enter. This information
    is provided in the persona sheet. We account for this in this function. 

    INPUT
      None
    OUTPUT 
      A summary string of all the arenas that the persona can access. 
    EXAMPLE STR OUTPUT
      "bedroom, kitchen, dining room, office, bathroom"
    """
    # 兼容传入的地址含有超过两个段位（如 world:sector:arena:object）
    try:
      parts = sector.split(":") if isinstance(sector, str) else []
      if len(parts) < 2:
        return ""
      curr_world, curr_sector = parts[0], parts[1]
      if not curr_sector:
        return ""
      x = ", ".join(list(self.tree[curr_world][curr_sector].keys()))
      return x
    except KeyError:
      # 目标 sector 不在记忆树中（例如传入了其他角色的公寓名）→ 返回空，避免 KeyError
      return ""
    except Exception:
      # 任意非关键错误，稳妥返回空字符串
      return ""


  def get_str_accessible_arena_game_objects(self, arena):
    """
    Get a str list of all accessible game objects that are in the arena. If 
    temp_address is specified, we return the objects that are available in
    that arena, and if not, we return the objects that are in the arena our
    persona is currently in. 

    INPUT
      temp_address: optional arena address
    OUTPUT 
      str list of all accessible game objects in the gmae arena. 
    EXAMPLE STR OUTPUT
      "phone, charger, bed, nightstand"
    """
    # 兼容多段地址 world:sector:arena[:object...]，仅取前三段
    try:
      parts = arena.split(":") if isinstance(arena, str) else []
      if len(parts) < 3:
        return ""
      curr_world, curr_sector, curr_arena = parts[0], parts[1], parts[2]

      if not curr_arena:
        return ""

      try:
        x = ", ".join(list(self.tree[curr_world][curr_sector][curr_arena]))
        return x
      except Exception:
        # Try with lower-case, then with braces/whitespace stripped，最后失败返回空
        try:
          x = ", ".join(list(self.tree[curr_world][curr_sector][curr_arena.lower()]))
          return x
        except Exception:
          _trim = curr_arena.strip().strip("{} ")
          try:
            x = ", ".join(list(self.tree[curr_world][curr_sector][_trim]))
            return x
          except Exception:
            try:
              x = ", ".join(list(self.tree[curr_world][curr_sector][_trim.lower()]))
              return x
            except Exception:
              return ""
    except Exception:
      # 任意解析/索引异常，返回空字符串避免上层崩溃
      return ""


if __name__ == '__main__':
  x = f"../../../../environment/frontend_server/storage/the_ville_base_LinFamily/personas/Eddy Lin/bootstrap_memory/spatial_memory.json"
  x = MemoryTree(x)
  x.print_tree()

  print (x.get_str_accessible_sector_arenas("dolores double studio:double studio"))







