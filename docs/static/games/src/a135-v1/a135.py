"""a135 Asymmetric Seed -- choose one equivalence class that produces traveling growth."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,CELL,SEED,GROWTH,COLLISION,TRAVEL,PHASE,EMPTY,BAD=1,8,7,12,10,6,4,13,11,15
LEVELS=[
 {"name":"Move Seed","seq":(1,)},{"name":"Rotate Pattern","seq":(2,)},
 {"name":"Change Growth Phase","seq":(3,1)},{"name":"Run Growth","seq":(1,2,3,4,2)},
 {"name":"Avoid Collision","seq":(1,3,2,1,4,3,2)},{"name":"Asymmetric Seed","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 seed,rotation,phase,cells,collisions,travel,history,snapshot=s
 if a==1:seed=(seed+1)%16;history=(history+(1,))[-8:]
 elif a==2:rotation=(rotation+1)%4;history=(history+(2,))[-8:]
 elif a==3:phase=(phase+1)%5;history=(history+(3,))[-8:]
 elif a==4:
  orbit={seed,15-seed,(seed%4)*4+seed//4};collisions=max(0,3-len(orbit)+(phase+rotation)%2);travel=int(len(orbit)==3 and collisions==0);cells=tuple(sorted((x+phase+rotation)%16 for x in orbit));history=(history+(4,))[-8:]
 elif a==5:snapshot=(seed,rotation,phase,cells,collisions,travel,history)
 return seed,rotation,phase,cells,collisions,travel,history,snapshot
for q in LEVELS:
 s=(0,0,0,(),3,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB
  for i in range(16):
   x=10+(i%4)*12;y=10+(i//4)*11;col=SEED if i==g.seed else GROWTH if i in g.cells else CELL;f[y:y+9,x:x+9]=col
  f[54:58,8:8+g.collisions*10]=COLLISION;f[54:58,43:55]=TRAVEL if g.travel else EMPTY;f[7:10,8:8+g.phase*8]=PHASE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A135(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a135",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.seed,self.rotation,self.phase,self.cells,self.collisions,self.travel,self.history,self.snapshot=(0,0,0,(),3,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.seed,self.rotation,self.phase,self.cells,self.collisions,self.travel,self.history,self.snapshot=advance((self.seed,self.rotation,self.phase,self.cells,self.collisions,self.travel,self.history,self.snapshot),a)
  elif a==6:
   if (self.seed,self.rotation,self.phase,self.cells,self.collisions,self.travel,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
