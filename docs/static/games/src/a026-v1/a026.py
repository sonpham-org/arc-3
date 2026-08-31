"""a026 Coupled Buttons -- discover chorded bindings with forbidden combinations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FLOOR,BUTTON,ACTIVE,PENDING,CHORD,FORBIDDEN,GOAL,BAD=5,10,14,11,6,12,8,13,15
LEVELS=[{"name":"First Primitive","seq":(1,3)},{"name":"Complete Chord","seq":(2,3)},{"name":"Button Binding","seq":(1,2,3)},{"name":"Forbidden Pair","seq":(4,2,1,3)},{"name":"Spatial Sequence","seq":(2,3,1,4,2,1,3)},{"name":"Coupled Buttons","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 pending,buttons,history,forbidden,phase,committed=s;b=list(buttons)
 if a==1:pending=(pending+1)%4
 elif a==2:
  chord=(pending,phase);idx=(pending+phase)%4
  if chord not in forbidden:b[idx]^=1
  history=history+((chord,idx,tuple(b)),);pending=-1
 elif a==3:history=history+(((pending,phase),sum(b)%4,tuple(b)),)
 elif a==4:phase=(phase+1)%4;pending=phase;forbidden=forbidden+(((phase+1)%4,phase),)
 elif a==5:committed=(pending,tuple(b),history[-5:],forbidden[-3:],phase)
 return pending,tuple(b),history,forbidden,phase,committed
for x in LEVELS:
 s=(-1,(0,0,0,0),(),((3,3),),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FLOOR
  for i,on in enumerate(g.buttons):x=10+(i%2)*28;y=10+(i//2)*18;f[y:y+13,x:x+18]=ACTIVE if on else BUTTON
  f[1:4,8:28]=CHORD
  if g.pending>=0:f[38:44,8:28]=PENDING
  for i,_ in enumerate(g.history[-3:]):f[48:53,8+i*14:18+i*14]=CHORD
  for i,_ in enumerate(g.forbidden[-2:]):f[55:59,8+i*18:22+i*18]=FORBIDDEN
  if g.committed:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A026(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a026",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pending=-1;self.buttons=(0,0,0,0);self.history=();self.forbidden=((3,3),);self.phase=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pending,self.buttons,self.history,self.forbidden,self.phase,self.committed=advance((self.pending,self.buttons,self.history,self.forbidden,self.phase,self.committed),a)
  elif a==6:
   if (self.pending,self.buttons,self.history,self.forbidden,self.phase,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
