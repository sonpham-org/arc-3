"""a122 Between Lines -- place one body to satisfy simultaneous ternary constraints."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,PLANE,END_A,END_B,MOVER,LINE,BETWEEN,ROTATE,MISS,BAD=3,8,12,14,10,9,4,13,6,15
LEVELS=[
 {"name":"Move Across","seq":(1,)},{"name":"Move Down","seq":(2,)},
 {"name":"Rotate Scene","seq":(3,1)},{"name":"Satisfy Two Lines","seq":(1,2,3,4,2)},
 {"name":"Intersect Constraints","seq":(1,3,2,1,4,3,2)},{"name":"Between Lines","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 x,y,rotation,satisfied,misses,history,snapshot=s
 if a==1:x=(x+1)%5;history=(history+(1,))[-8:]
 elif a==2:y=(y+1)%5;history=(history+(2,))[-8:]
 elif a==3:rotation=(rotation+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  targets=((2,2),(3,1),(2,3),(1,2));tx,ty=targets[rotation];satisfied=int(x==tx)+int(y==ty)+int((x+y)%4==(tx+ty)%4);misses=3-satisfied;history=(history+(4,))[-8:]
 elif a==5:snapshot=(x,y,rotation,satisfied,misses,history)
 return x,y,rotation,satisfied,misses,history,snapshot
for q in LEVELS:
 s=(0,0,0,0,3,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=PLANE
  pairs=(((9,12),(54,48)),((9,48),(54,12)),((9,30),(54,30)))
  for i,((x1,y1),(x2,y2)) in enumerate(pairs):
   f[min(y1,y2):max(y1,y2)+1,min(x1,x2):max(x1,x2)+1]=LINE;f[y1-3:y1+4,x1-3:x1+4]=END_A;f[y2-3:y2+4,x2-3:x2+4]=END_B
  px=12+g.x*10;py=12+g.y*9;f[py-4:py+5,px-4:px+5]=MOVER;f[py-7:py-5,px-6:px+7]=ROTATE
  f[54:58,8:8+g.satisfied*13]=BETWEEN;f[7:10,8:8+g.misses*10]=MISS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A122(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a122",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.x,self.y,self.rotation,self.satisfied,self.misses,self.history,self.snapshot=(0,0,0,0,3,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.x,self.y,self.rotation,self.satisfied,self.misses,self.history,self.snapshot=advance((self.x,self.y,self.rotation,self.satisfied,self.misses,self.history,self.snapshot),a)
  elif a==6:
   if (self.x,self.y,self.rotation,self.satisfied,self.misses,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
