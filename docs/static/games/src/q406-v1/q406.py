"""q406 Crossing Delegation -- alternate disjoint passenger and dock views through marks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,BANK,FERRY,PASSENGER,DOCK,CONTROL,MARK,INTEGRATE,BAD=12,10,11,0,15,9,14,6,7,8
LEVELS=[
 {"name":"Split Views","plan":(1,3,4,2,3,5)},
 {"name":"Remote Dock","plan":(2,3,4,1,3,5)},
 {"name":"Alternating Marks","plan":(1,2,3,4,2,3,5)},
 {"name":"Capacity Projection","plan":(2,1,3,4,1,2,3,5)},
 {"name":"Disjoint Evidence","plan":(1,3,4,2,1,3,4,2,3,5)},
 {"name":"Crossing Delegation","plan":(2,1,3,4,1,3,4,2,3,5,4,1)}]
def advance(s,a):
 controller,pk,dk,marks,integrated=s;pk=list(pk);dk=list(dk);marks=list(marks)
 if a==1:pk[controller]|=1<<((controller+sum(pk)+1)%4)
 elif a==2:dk[controller]|=1<<((controller+sum(dk)+2)%4)
 elif a==3:marks[controller]=(pk[controller]*3+dk[controller]+controller+1)%8
 elif a==4:controller=1-controller
 elif a==5:integrated=(marks[0]^marks[1]^pk[0]^dk[1])%8
 return controller,tuple(pk),tuple(dk),tuple(marks),integrated
def target(x):
 s=(0,(0,0),(0,0),(0,0),0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[9:55,3:61]=RIVER;f[5:11,:]=BANK;f[53:60,:]=BANK;f[28:38,22:43]=FERRY
  for i in range(2):
   f[15+i*23:18+i*23,8:18]=PASSENGER;f[19+i*23:22+i*23,8:8+g.pk[i]*4]=PASSENGER
   f[23+i*17:26+i*17,41:51]=DOCK;f[27+i*17:30+i*17,41:41+g.dk[i]*3]=DOCK;f[12+i*31:15+i*31,9:9+max(1,g.marks[i])*5]=MARK
  f[57:60,8:8+g.controller*22]=CONTROL;f[48:51,8:8+g.integrated*6]=INTEGRATE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q406(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset()
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q406",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.pk=(0,0);self.dk=(0,0);self.marks=(0,0);self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.controller,self.pk,self.dk,self.marks,self.integrated=advance((self.controller,self.pk,self.dk,self.marks,self.integrated),a)
  elif a==6:
   if (self.controller,self.pk,self.dk,self.marks,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
