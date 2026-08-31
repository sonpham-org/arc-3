"""q524 Tessera Frame -- compose tile motion across rotating, topology-changing mosaic seams."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TILE,SEAM,FRAME,FOLD,LOCK,GOAL,BAD=0,9,14,10,6,11,12,13,15
LEVELS=[
 {"name":"Local Tessera","seq":(1,)},{"name":"Rotated Seam","seq":(2,1)},
 {"name":"First Fold","seq":(1,3,2)},{"name":"Moving Frame","seq":(2,1,4,3)},
 {"name":"Topology Exchange","seq":(1,2,3,4,1,2)},
 {"name":"Tessera Frame","seq":(2,1,4,3,2,1,3,4,1)}]
def advance(s,a):
 tile,seam,rotation,fold,locked=s
 if a==1:tile=(tile+1+rotation+fold)%9
 elif a==2:rotation=(rotation+1)%4;seam=(seam+rotation)%6
 elif a==3:fold=(fold+1)%3;tile=(8-tile+seam)%9
 elif a==4:seam=(seam+2+fold)%6;rotation=(rotation+seam)%4
 elif a==5:locked=(tile,seam,rotation,fold)
 return tile,seam,rotation,fold,locked
for x in LEVELS:
 s=(0,0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MOSAIC
  for i in range(9):
   x=8+(i%3)*17;y=8+(i//3)*12;f[y:y+9,x:x+13]=TILE if i==g.tile else FRAME
   if (i+g.seam)%3==0:f[y:y+2,x:x+13]=SEAM
  f[46:50,8:8+g.rotation*11+7]=FOLD;f[53:57,8:8+g.fold*15+10]=LOCK
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q524(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q524",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tile=self.seam=self.rotation=self.fold=0;self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tile,self.seam,self.rotation,self.fold,self.locked=advance((self.tile,self.seam,self.rotation,self.fold,self.locked),a)
  elif a==6:
   if (self.tile,self.seam,self.rotation,self.fold,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
