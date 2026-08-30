"""q050 Compression Cabinet -- store a few reusable tiles that explain later patterns."""
from copy import deepcopy
from itertools import combinations
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CABINET,TILE,STORED,QUERY,CURSOR,SLOT,BAD=15,4,10,14,9,11,12,8
LEVELS=[
 {"name":"Store One Pattern","tiles":[1,2],"queries":[1],"solution":[0]},
 {"name":"Compose Two Tiles","tiles":[1,2,4],"queries":[1,2,3],"solution":[0,1]},
 {"name":"Reusable Parts","tiles":[1,2,4,3],"queries":[3,5,6,7],"solution":[0,1,2]},
 {"name":"Reject Redundancy","tiles":[1,2,4,8,3],"queries":[5,9,10,12],"solution":[0,1,2,3]},
 {"name":"Transformation Basis","tiles":[1,2,4,8,5,10],"queries":[3,6,9,12,15],"solution":[0,1,2,3]},
 {"name":"Compression Cabinet","tiles":[1,2,4,8,16,3,12],"queries":[7,11,13,19,28,31],"solution":[0,1,2,3,4]}]
def explains(query,tiles):
 return any(__import__("functools").reduce(int.__xor__,c,0)==query for n in range(1,len(tiles)+1) for c in combinations(tiles,n))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CABINET;n=len(g.tiles)
  for i,t in enumerate(g.tiles):x=7+i*(50//n);f[16:29,x:x+7]=STORED if i in g.stored else TILE;f[12:15,x:x+7]=CURSOR if i==g.cursor else CABINET;f[23:26,x:x+min(7,t.bit_count()+2)]=QUERY
  for i,q in enumerate(g.queries):x=7+i*8;f[38:46,x:x+6]=QUERY;f[49:52,x:x+6]=STORED if explains(q,[g.tiles[j] for j in g.stored]) else SLOT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q050(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.tiles=self.queries=[];self.solution=[];self.stored=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q050",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.tiles=list(s["tiles"]);self.queries=list(s["queries"]);self.solution=list(s["solution"]);self.stored=[];self.cursor=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==3:self.cursor=(self.cursor-1)%len(self.tiles)
  elif z==4:self.cursor=(self.cursor+1)%len(self.tiles)
  elif z==5:
   if self.cursor in self.stored:self.stored.remove(self.cursor)
   elif len(self.stored)<len(self.solution):self.stored.append(self.cursor)
   else:self.failed=True;self.lose()
  elif z==6:
   chosen=[self.tiles[i] for i in self.stored]
   if len(self.stored)<=len(self.solution) and all(explains(q,chosen) for q in self.queries):self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
