"""q506 Palimpsest Frame -- use a failed example to compose moving archive frames."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,TILE,FRAME,TRACE,EXAMPLE,GOAL,BAD=9,10,12,14,5,11,6,7,15
LEVELS=[{"name":"Local Trace","plan":(1,5)},{"name":"Translated Shelf","plan":(2,4,1,5)},{"name":"Rotated Archive","plan":(3,1,2,5)},{"name":"Failed Gesture","plan":(1,4,3,2,5,1)},{"name":"Overwritten Frame","plan":(2,3,5,4,1,2,5)},{"name":"Palimpsest Frame","plan":(3,1,4,2,5,3,1,5)}]
def advance(s,a):
 tiles,rotation,offset,traces,mismatch=s;tiles=list(tiles);traces=list(traces)
 if a in (1,2):i=(a-1+rotation)%3;tiles[i]=(tiles[i]+(1 if a==1 else -1)+offset)%5
 elif a==3:rotation=(rotation+1)%4;tiles=tiles[1:]+tiles[:1]
 elif a==4:offset=(offset+1)%5;tiles=[(v+offset)%5 for v in tiles]
 elif a==5:
  failed=(sum(tiles)+rotation+offset+1)%5;actual=(tiles[rotation%3]+offset)%5;mismatch=(mismatch+(failed!=actual))%4;traces.append((failed,actual))
 return tuple(tiles),rotation,offset,tuple(traces),mismatch
def target(x):
 s=((0,2,4),0,0,(),0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE
  for i,v in enumerate(g.tiles):x=8+i*18;f[9:39,x:x+13]=SHELF;f[14+v*5:20+v*5,x+3:x+10]=TILE-i
  f[42:45,8:11+g.rotation*11]=FRAME;f[48:51,8:11+g.offset*10]=TRACE
  for i,(failed,actual) in enumerate(g.traces[-3:]):x=9+i*17;f[54:57,x:x+6]=EXAMPLE;f[57:60,x:x+6+actual*2]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q506(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q506",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tiles=(0,2,4);self.rotation=self.offset=self.mismatch=0;self.traces=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tiles,self.rotation,self.offset,self.traces,self.mismatch=advance((self.tiles,self.rotation,self.offset,self.traces,self.mismatch),a)
  elif a==6:
   if (self.tiles,self.rotation,self.offset,self.traces,self.mismatch)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
