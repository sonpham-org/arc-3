"""a184 Proof by Tiling -- decompose a region into locally verifiable primitives."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,REGION,TILE_A,TILE_B,PRIMITIVE,ROTATE,CURSOR,VALID,INVALID,GAP=5,8,12,14,10,13,11,4,6,7
BAD=15
LEVELS=[
 {"name":"Place Primitive","seq":(1,)},{"name":"Select Cell","seq":(2,)},
 {"name":"Rotate Primitive","seq":(3,1)},{"name":"Verify Decomposition","seq":(1,2,3,4,2)},
 {"name":"Reject Area Shortcut","seq":(1,3,2,1,4,3,2)},{"name":"Proof by Tiling","seq":(1,2,3,1,4,2,3,1,4,3)},
]
TARGET=(0,1,0,1,1,0,1,0,1)
def advance(s,a):
 tiles,cursor,rotation,valid,invalid,gaps,history,snapshot=s;t=list(tiles)
 if a==1:t[cursor]=(t[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%9;history=(history+(2,))[-8:]
 elif a==3:rotation=(rotation+1)%4;history=(history+(3,))[-8:]
 elif a==4:valid=sum(int(t[i]%2==TARGET[(i+rotation)%9]) for i in range(9));invalid=sum(int(x==2) for x in t);gaps=9-valid;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(t),cursor,rotation,valid,invalid,gaps,history)
 return tuple(t),cursor,rotation,valid,invalid,gaps,history,snapshot
for q in LEVELS:
 s=((0,1,0,1,1,0,1,0,1),0,0,9,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REGION;cols=(TILE_A,TILE_B,INVALID)
  for i,v in enumerate(g.tiles):
   x=11+(i%3)*16;y=12+(i//3)*15;f[y:y+11,x:x+11]=cols[v];f[y+3:y+8,x+3:x+8]=PRIMITIVE
   if i==g.cursor:f[y-3:y,x:x+11]=CURSOR
  f[54:58,8:8+g.valid*5]=VALID;f[7:10,8:8+g.invalid*7]=INVALID;f[54:58,51:51+g.gaps]=GAP
  if g.bad:f[1:4,18:46]=BAD
  return f
class A184(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a184",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tiles,self.cursor,self.rotation,self.valid,self.invalid,self.gaps,self.history,self.snapshot=((0,1,0,1,1,0,1,0,1),0,0,9,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tiles,self.cursor,self.rotation,self.valid,self.invalid,self.gaps,self.history,self.snapshot=advance((self.tiles,self.cursor,self.rotation,self.valid,self.invalid,self.gaps,self.history,self.snapshot),a)
  elif a==6:
   if (self.tiles,self.cursor,self.rotation,self.valid,self.invalid,self.gaps,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
