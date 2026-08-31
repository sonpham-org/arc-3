"""a064 Coupled Controllers -- tune two regulators that fight through one platform."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,PLATFORM,CTRL_A,CTRL_B,GAIN,COUPLE,SETTLE,ERROR,BAD=8,9,4,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Tune Left","seq":(1,)},{"name":"Tune Right","seq":(2,)},
 {"name":"Observe Coupling","seq":(1,2,3)},{"name":"Reduce Oscillation","seq":(1,3,2,3,4)},
 {"name":"Shared Platform","seq":(1,2,3,4,1,3,2)},{"name":"Coupled Controllers","seq":(1,3,2,4,3,1,2,3,4,3)},
]
def advance(s,a):
 sides,gains,coupling,phase,stable,history,snapshot=s;sd=list(sides);g=list(gains)
 if a==1:g[0]=(g[0]+1)%4;history=(history+(1,))[-8:]
 elif a==2:g[1]=(g[1]+1)%4;history=(history+(2,))[-8:]
 elif a==3:
  e0=3-sd[0];e1=3-sd[1];sd[0]=max(0,min(6,sd[0]+(1 if e0>0 else -1 if e0<0 else 0)*g[0]-(coupling if phase else 0)));sd[1]=max(0,min(6,sd[1]+(1 if e1>0 else -1 if e1<0 else 0)*g[1]+(coupling if phase else 0)));phase^=1;stable=min(5,stable+1) if abs(sd[0]-3)<=1 and abs(sd[1]-3)<=1 else 0;history=(history+(3,))[-8:]
 elif a==4:coupling=(coupling+1)%3;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(sd),tuple(g),coupling,phase,stable,history)
 return tuple(sd),tuple(g),coupling,phase,stable,history,snapshot
for x in LEVELS:
 s=((1,5),(1,1),1,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;f[27:37,8:56]=PLATFORM
  for i,col in enumerate((CTRL_A,CTRL_B)):
   x=10+i*32;y=33-g.sides[i]*3;f[y:y+10,x:x+12]=col
   for j in range(g.gains[i]):f[45+j*3:47+j*3,x:x+12]=GAIN
  f[22:42,29:35]=COUPLE;f[17:21,29:29+g.coupling*8]=ERROR
  for i in range(g.stable):f[54:58,9+i*9:16+i*9]=SETTLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A064(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a064",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sides,self.gains,self.coupling,self.phase,self.stable,self.history,self.snapshot=((1,5),(1,1),1,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.sides,self.gains,self.coupling,self.phase,self.stable,self.history,self.snapshot=advance((self.sides,self.gains,self.coupling,self.phase,self.stable,self.history,self.snapshot),a)
  elif a==6:
   if (self.sides,self.gains,self.coupling,self.phase,self.stable,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
