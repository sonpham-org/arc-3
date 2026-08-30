"""q057 Raft Shape -- construct buoyant footprints that fit cargo and channels."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,TILE,CARGO,BANK,TARGET,CURSOR,BAD=10,6,12,9,4,14,11,8
LEVELS=[
 {"name":"Cargo Support","target":[(1,1),(2,1)]},
 {"name":"Stable Triangle","target":[(1,1),(2,1),(1,2)]},
 {"name":"Narrow Channel","target":[(0,1),(1,1),(2,1),(3,1)]},
 {"name":"Balanced Cargo","target":[(1,0),(1,1),(2,1),(1,2),(2,2)]},
 {"name":"Split Current","target":[(0,1),(1,1),(2,1),(2,2),(3,2),(4,2)]},
 {"name":"Raft Shape","target":[(1,0),(2,0),(1,1),(2,1),(3,1),(2,2),(3,2),(2,3)]}]
W,H=5,4
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=WATER;f[8:12,4:60]=BANK;f[52:56,4:60]=BANK
  for y in range(H):
   for x in range(W):
    x0,y0=9+x*10,12+y*10;f[y0:y0+8,x0:x0+8]=TILE if (x,y) in g.tiles else WATER
    if (x,y)==g.cursor:f[y0:y0+2,x0:x0+8]=CURSOR
    if (x,y) in g.target:f[y0+5:y0+8,x0+2:x0+6]=TARGET
  cx=sum(x for x,y in g.target)//len(g.target);f[4:8,9+cx*10:17+cx*10]=CARGO
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q057(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=set();self.tiles=set();self.cursor=(0,0);self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q057",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.target=set(map(tuple,LEVELS[self.level_index]["target"]));self.tiles=set();self.cursor=(0,0);self.failed=False
 def step(self):
  a=self.action.id.value;x,y=self.cursor
  if a==0:self.complete_action();return
  if a==1:y=max(0,y-1);self.cursor=(x,y)
  elif a==2:y=min(H-1,y+1);self.cursor=(x,y)
  elif a==3:x=max(0,x-1);self.cursor=(x,y)
  elif a==4:x=min(W-1,x+1);self.cursor=(x,y)
  elif a==5:
   if self.cursor in self.tiles:self.tiles.remove(self.cursor)
   else:self.tiles.add(self.cursor)
  elif a==6:
   if self.tiles==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
