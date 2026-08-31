"""a194 Bus Backplane -- schedule plug-in modules on one collision-prone bus."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,RACK,MODULE_A,MODULE_B,MODULE_C,MODULE_D,BUS,CURSOR,CLEAR,COLLIDE=3,1,12,14,10,8,5,13,4,6
BAD=15
LEVELS=[
 {"name":"Assign Slot","seq":(1,)},{"name":"Choose Module","seq":(2,)},
 {"name":"Shift Clock","seq":(3,1)},{"name":"Detect Collision","seq":(1,2,3,4,2)},
 {"name":"Pair Exchange","seq":(1,3,2,1,4,3,2)},{"name":"Bus Backplane","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 slots,cursor,phase,clear,collisions,history,snapshot=s;x=list(slots)
 if a==1:x[cursor]=(x[cursor]+1)%6;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:phase=(phase+1)%6;history=(history+(3,))[-8:]
 elif a==4:collisions=sum(int(x[i]==x[j]) for i in range(4) for j in range(i));clear=6-collisions;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(x),cursor,phase,clear,collisions,history)
 return tuple(x),cursor,phase,clear,collisions,history,snapshot
for q in LEVELS:
 s=((0,2,4,5),0,0,6,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=RACK;f[29:35,8:56]=BUS
  cols=(MODULE_A,MODULE_B,MODULE_C,MODULE_D)
  for i,slot in enumerate(g.slots):
   x=9+i*12;f[10:23,x:x+9]=cols[i];sx=9+slot*8;f[39+i*3:41+i*3,sx:sx+7]=cols[i]
   if i==g.cursor:f[7:10,x:x+9]=CURSOR
  f[25:28,9+g.phase*8:16+g.phase*8]=CURSOR;f[54:58,8:8+min(6,g.clear)*6]=CLEAR;f[54:58,47:47+min(3,g.collisions)*4]=COLLIDE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A194(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a194",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots,self.cursor,self.phase,self.clear,self.collisions,self.history,self.snapshot=((0,2,4,5),0,0,6,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.slots,self.cursor,self.phase,self.clear,self.collisions,self.history,self.snapshot=advance((self.slots,self.cursor,self.phase,self.clear,self.collisions,self.history,self.snapshot),a)
  elif a==6:
   if (self.slots,self.cursor,self.phase,self.clear,self.collisions,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
