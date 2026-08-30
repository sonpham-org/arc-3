"""q105 Orbiting Board -- exchange pieces only when rotating local edge cells align globally."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SPACE,BOARD,PIECE,ALIGN,TARGET,CURSOR,BAD=2,0,10,6,14,9,12,8
LEVELS=[
 {"name":"First Alignment","start":[2,0],"target":[1,1],"period":2,"align":[0]}, {"name":"Wait for Edge","start":[3,0],"target":[1,2],"period":3,"align":[1]},
 {"name":"Three Boards","start":[3,0,0],"target":[1,1,1],"period":3,"align":[0,1]}, {"name":"Orbit Exchange","start":[4,0,0],"target":[1,2,1],"period":4,"align":[1,3]},
 {"name":"Staggered Edges","start":[3,1,0,0],"target":[1,1,1,1],"period":5,"align":[0,2,4]}, {"name":"Orbiting Board","start":[4,1,0,0],"target":[1,1,2,1],"period":6,"align":[1,3,5]}]
def transfer(vals,i):
 o=list(vals);j=(i+1)%len(o)
 if o[i]:o[i]-=1;o[j]+=1
 return tuple(o)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=SPACE;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):x=9+i*(47//n);f[20:39,x:x+10]=BOARD;f[22:22+v*4,x+2:x+8]=PIECE;f[14:17,x:x+t*3]=TARGET
  f[43:47,7+g.cursor*(47//n):16+g.cursor*(47//n)]=CURSOR;f[3:6,7+g.phase*7:13+g.phase*7]=ALIGN if g.phase in g.align else BOARD
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q105(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.period=self.phase=self.cursor=0;self.align=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q105",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.period=s["period"];self.align=set(s["align"]);self.phase=self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.values)
  elif a==4:self.cursor=(self.cursor+1)%len(self.values)
  elif a==5:self.phase=(self.phase+1)%self.period
  elif a==1 and self.phase in self.align:self.values=transfer(self.values,self.cursor)
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
