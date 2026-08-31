"""a129 Canonical Room -- use an external anchor to choose one symmetry representative."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GALLERY,ROOM,SHAPE,ANCHOR,ROTATE,REFLECT,CANONICAL,MISMATCH,BAD=11,8,7,12,14,10,13,4,6,15
LEVELS=[
 {"name":"Rotate Room","seq":(1,)},{"name":"Reflect Room","seq":(2,)},
 {"name":"Select Room","seq":(3,1)},{"name":"Read Anchor","seq":(1,2,3,4,2)},
 {"name":"Choose Normal Form","seq":(1,3,2,1,4,3,2)},{"name":"Canonical Room","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 transforms,cursor,anchor,canonical,mismatch,history,snapshot=s;t=list(transforms)
 if a==1:t[cursor]=(t[cursor]//4)*4+(t[cursor]+1)%4;history=(history+(1,))[-8:]
 elif a==2:t[cursor]^=4;history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%4;anchor=(anchor+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  canonical=sum(int((x%4)==((anchor+i)%4) and x<4) for i,x in enumerate(t));mismatch=4-canonical;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(t),cursor,anchor,canonical,mismatch,history)
 return tuple(t),cursor,anchor,canonical,mismatch,history,snapshot
for q in LEVELS:
 s=((0,1,2,3),0,0,4,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  origins=((8,10),(35,10),(8,36),(35,36))
  for i,(x,y) in enumerate(origins):
   f[y:y+20,x:x+20]=ROOM;tr=g.transforms[i];corners=((x+3,y+3),(x+14,y+3),(x+14,y+14),(x+3,y+14));sx,sy=corners[tr%4];f[sy:sy+4,sx:sx+4]=SHAPE;f[y+8:y+12,x+8:x+12]=REFLECT if tr>=4 else ROTATE
   if i==g.cursor:f[y-3:y,x:x+20]=ANCHOR
  ax,ay=((30,5),(59,31),(30,57),(5,31))[g.anchor];f[max(0,ay-3):min(64,ay+4),max(0,ax-3):min(64,ax+4)]=ANCHOR
  f[54:58,8:8+g.canonical*9]=CANONICAL;f[7:10,8:8+g.mismatch*9]=MISMATCH
  if g.bad:f[1:4,18:46]=BAD
  return f
class A129(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a129",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.transforms,self.cursor,self.anchor,self.canonical,self.mismatch,self.history,self.snapshot=((0,1,2,3),0,0,4,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.transforms,self.cursor,self.anchor,self.canonical,self.mismatch,self.history,self.snapshot=advance((self.transforms,self.cursor,self.anchor,self.canonical,self.mismatch,self.history,self.snapshot),a)
  elif a==6:
   if (self.transforms,self.cursor,self.anchor,self.canonical,self.mismatch,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
