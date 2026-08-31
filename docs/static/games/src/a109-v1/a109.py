"""a109 Hinged Packing -- fold connected panels along collision-free paths."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SHOP,BIN,PANEL_A,PANEL_B,HINGE,SWEEP,COLLIDE,PLACED,BAD=5,8,9,12,14,10,11,4,13,15
LEVELS=[
 {"name":"Rotate Hinge","seq":(1,)},{"name":"Select Joint","seq":(3,)},
 {"name":"Reverse Fold","seq":(2,1)},{"name":"Avoid Sweep","seq":(1,3,2,4,1)},
 {"name":"Reach Compact","seq":(1,3,1,2,4,3,2)},{"name":"Hinged Packing","seq":(1,3,2,1,4,3,1,2,4,1)},
]
def advance(s,a):
 angles,cursor,span,collisions,placed,path,history,snapshot=s;an=list(angles)
 if a==1:an[cursor]=(an[cursor]+1)%4;path=(path+(tuple(an),))[-7:];history=(history+(1,))[-8:]
 elif a==2:an[cursor]=(an[cursor]-1)%4;path=(path+(tuple(an),))[-7:];history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%3;history=(history+(3,))[-8:]
 elif a==4:span=1+sum(int(x in (0,2)) for x in an);collisions=(collisions+sum(int(an[i]==an[i+1]) for i in range(2)))%6;placed=(placed+int(span<=3 and collisions==0))%5;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(an),cursor,span,collisions,placed,path,history)
 return tuple(an),cursor,span,collisions,placed,path,history,snapshot
for x in LEVELS:
 s=((0,1,2),0,4,0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP;f[15:49,36:58]=BIN;x,y=12,31
  dirs=((10,0),(0,-10),(-10,0),(0,10))
  for i,a in enumerate(g.angles):dx,dy=dirs[a];nx=x+dx;ny=y+dy;f[min(y,ny)-4:max(y,ny)+5,min(x,nx)-4:max(x,nx)+5]=PANEL_A if i%2==0 else PANEL_B;f[y-3:y+4,x-3:x+4]=HINGE;x,y=nx,ny
  f[8:12,8+g.cursor*12:18+g.cursor*12]=SWEEP
  for i in range(g.collisions):f[53:57,8+i*6:13+i*6]=COLLIDE
  for i in range(g.placed):f[53:57,43+i*3:46+i*3]=PLACED
  if g.bad:f[1:4,18:46]=BAD
  return f
class A109(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a109",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.angles,self.cursor,self.span,self.collisions,self.placed,self.path,self.history,self.snapshot=((0,1,2),0,4,0,0,(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.angles,self.cursor,self.span,self.collisions,self.placed,self.path,self.history,self.snapshot=advance((self.angles,self.cursor,self.span,self.collisions,self.placed,self.path,self.history,self.snapshot),a)
  elif a==6:
   if (self.angles,self.cursor,self.span,self.collisions,self.placed,self.path,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
