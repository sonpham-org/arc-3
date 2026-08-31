"""a043 Atomic Crossing -- stage coupled lock changes and commit them together."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,WATER,BRIDGE,LOCK_A,LOCK_B,CLAMP,CART,SAFE,WAKE,BAD=3,8,9,12,14,11,10,13,6,15
LEVELS=[
 {"name":"Select Lock","seq":(1,3)},{"name":"Coupled Pair","seq":(1,2,3)},
 {"name":"Atomic Commit","seq":(1,2,3,4)},{"name":"Restage","seq":(1,3,2,3,4)},
 {"name":"Crossing Window","seq":(2,1,3,4,1,3,4)},{"name":"Atomic Crossing","seq":(1,2,3,4,2,3,1,3,4)},
]
def advance(s,a):
 locks,selected,staged,cart,history,crossed=s;lk=list(locks)
 if a==1:selected^=1;history=(history+(1,))[-8:]
 elif a==2:selected^=2;history=(history+(2,))[-8:]
 elif a==3:staged^=selected;history=(history+(3,))[-8:]
 elif a==4:
  for i in range(2):
   if staged&(1<<i):lk[i]^=1
  selected=staged=0;cart=(cart+1+int(lk[0]==lk[1]))%6;history=(history+(4,))[-8:]
 elif a==5:crossed=(tuple(lk),selected,staged,cart,history)
 return tuple(lk),selected,staged,cart,history,crossed
for x in LEVELS:
 s=((0,0),0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=WATER;f[27:38,5:59]=BRIDGE
  for i,v in enumerate(g.locks):x=17+i*25;f[17:26,x:x+9]=LOCK_A if i==0 else LOCK_B;f[19:24,x+2:x+7]=SAFE if v else BRIDGE
  for i in range(2):
   if g.selected&(1<<i):x=17+i*25;f[12:16,x:x+9]=CLAMP
   if g.staged&(1<<i):x=17+i*25;f[39:43,x:x+9]=CLAMP
  x=7+g.cart*8;f[28:37,x:x+7]=CART
  for i,v in enumerate(g.history[-8:]):f[50:54,10+i*5:14+i*5]=WAKE if v==4 else CLAMP
  if g.bad:f[1:4,18:46]=BAD
  return f
class A043(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a043",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.locks,self.selected,self.staged,self.cart,self.history,self.crossed=((0,0),0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.locks,self.selected,self.staged,self.cart,self.history,self.crossed=advance((self.locks,self.selected,self.staged,self.cart,self.history,self.crossed),a)
  elif a==6:
   if (self.locks,self.selected,self.staged,self.cart,self.history,self.crossed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
