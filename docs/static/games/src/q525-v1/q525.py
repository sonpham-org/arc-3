"""q525 Vivarium Frame -- compose local motion with rotating strata and partner reciprocity."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VIVARIUM,STRATA,FAUNA,FRAME,FAVOR,GOAL,BAD=0,1,11,15,14,12,13,8
LEVELS=[
 {"name":"First Stratum","plan":(2,5,1)},{"name":"Reciprocal Turn","plan":(5,2,3,1)},
 {"name":"Moving Habitat","plan":(4,5,2,1,3)},{"name":"Coupled Frame","plan":(2,1,5,4,2,3)},
 {"name":"Fair Exchange","plan":(5,1,2,5,4,3,2)},{"name":"Vivarium Frame","plan":(2,5,4,1,5,3,2,4)}]
V=((0,-1),(1,0),(0,1),(-1,0))
def advance(s,a):
 pos,offset,rot,favor=s;x,y=pos
 if a==5:favor=(favor+1)%3;rot=(rot+favor)%4;offset=(offset+1)%5
 else:
  dx,dy=V[(a-1+rot)%4];x=(x+dx+offset)%5;y=(y+dy+favor)%5;offset=(offset+favor)%5
 return (x,y),offset,rot,favor
def target(x):
 s=((2,2),0,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=VIVARIUM
  for i in range(6):f[9+i*7:12+i*7,8:56]=STRATA
  x,y=g.pos;f[11+y*7:16+y*7,10+x*9:17+x*9]=FAUNA;tx,ty=g.target[0];f[10+ty*7:12+ty*7,9+tx*9:18+tx*9]=GOAL
  f[50:53,8:8+g.rot*11]=FRAME;f[55:59,8:8+g.favor*14]=FAVOR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q525(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.pos=(2,2);self.offset=self.rot=self.favor=0;self.target=target(LEVELS[0]);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q525",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.pos=(2,2);self.offset=self.rot=self.favor=0;self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.offset,self.rot,self.favor=advance((self.pos,self.offset,self.rot,self.favor),a)
  elif a==6:
   if (self.pos,self.offset,self.rot,self.favor)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
