"""q033 Color Exchange -- reach exact objects by swapping conserved components."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,EDGE,A,B,TARGET,CURSOR,BAD=14,1,3,9,6,11,12,8
LEVELS=[
 {"name":"One Swap","start":[(1,0),(0,1)],"target":[(0,0),(1,1)],"ops":[(0,1,0)]},
 {"name":"Two Components","start":[(1,0),(0,1)],"target":[(0,1),(1,0)],"ops":[(0,1,0),(0,1,1)]},
 {"name":"Three Objects","start":[(1,1),(0,0),(1,0)],"target":[(0,1),(1,0),(1,0)],"ops":[(0,1,0),(1,2,1),(0,2,0)]},
 {"name":"Exchange Ring","start":[(1,0),(0,1),(1,1)],"target":[(0,1),(1,1),(1,0)],"ops":[(0,1,0),(1,2,1),(2,0,0),(0,2,1)]},
 {"name":"Conserved Ledger","start":[(1,1),(1,0),(0,1),(0,0)],"target":[(0,1),(1,1),(0,0),(1,0)],"ops":[(0,1,0),(1,2,1),(2,3,0),(3,0,1),(0,2,0)]},
 {"name":"Color Exchange","start":[(1,0),(0,1),(1,1),(0,0)],"target":[(0,1),(1,0),(0,1),(1,0)],"ops":[(0,1,0),(1,2,1),(2,3,0),(3,0,1),(0,2,0),(1,3,1)]}]
def swap(vals,op):
 i,j,k=op;o=[list(v) for v in vals];o[i][k],o[j][k]=o[j][k],o[i][k];return tuple(map(tuple,o))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=HALL;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=9+i*(48//n);f[18:34,x:x+9]=EDGE;f[20:32,x+2:x+4]=A if v[0] else HALL;f[20:32,x+5:x+7]=B if v[1] else HALL
   f[11:14,x:x+4]=TARGET if v[0]==t[0] else A;f[11:14,x+5:x+9]=TARGET if v[1]==t[1] else B
  for i in range(len(g.ops)):f[44:49,6+i*8:12+i*8]=CURSOR if i==g.cursor else EDGE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q033(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.ops=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q033",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.ops=list(s["ops"]);self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.ops)
  elif a==4:self.cursor=(self.cursor+1)%len(self.ops)
  elif a==5:self.values=swap(self.values,self.ops[self.cursor])
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
