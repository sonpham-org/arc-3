"""a072 Moire Current -- steer with coarse interference from fine stripe layers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,TANK,STRIPE_A,STRIPE_B,BAND,PARTICLE,CHANNEL,SHIFT,GOAL,BAD=0,8,9,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Shift Layer A","seq":(1,)},{"name":"Shift Layer B","seq":(2,)},
 {"name":"Reveal Band","seq":(1,2,3)},{"name":"Follow Current","seq":(1,1,2,3,4)},
 {"name":"Invisible Channel","seq":(2,1,3,4,1,3,4)},{"name":"Moire Current","seq":(1,2,3,1,4,2,3,4,1,4)},
]
def advance(s,a):
 offsets,particle,phase,current,trail,history,snapshot=s;o=list(offsets);p=list(particle)
 if a==1:o[0]=(o[0]+1)%5;history=(history+(1,))[-8:]
 elif a==2:o[1]=(o[1]+2)%7;history=(history+(2,))[-8:]
 elif a==3:current=((o[1]-o[0]+phase)%3)-1;phase^=1;trail=(trail+(current,))[-7:];history=(history+(3,))[-8:]
 elif a==4:p[0]=max(0,min(9,p[0]+1));p[1]=(p[1]+current)%7;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(o),tuple(p),phase,current,trail,history)
 return tuple(o),tuple(p),phase,current,trail,history,snapshot
for x in LEVELS:
 s=((0,1),(0,3),0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TANK
  for x in range(6+g.offsets[0],59,5):f[7:55,x:x+1]=STRIPE_A
  for y in range(7+g.offsets[1],55,7):f[y:y+1,6:59]=STRIPE_B
  for k in range(3):y=15+k*14+(g.offsets[1]-g.offsets[0])%5;f[y:y+3,7:58]=BAND
  x=8+g.particle[0]*5;y=10+g.particle[1]*6;f[y:y+6,x:x+6]=PARTICLE
  f[55:58,8:8+len(g.trail)*6]=CHANNEL;f[7:11,48:57]=SHIFT;f[47:54,54:58]=GOAL
  if g.bad:f[1:4,18:46]=BAD
  return f
class A072(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a072",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.offsets,self.particle,self.phase,self.current,self.trail,self.history,self.snapshot=((0,1),(0,3),0,0,(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.offsets,self.particle,self.phase,self.current,self.trail,self.history,self.snapshot=advance((self.offsets,self.particle,self.phase,self.current,self.trail,self.history,self.snapshot),a)
  elif a==6:
   if (self.offsets,self.particle,self.phase,self.current,self.trail,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
