"""q283 Impeller Probe -- distinguish wake causes before redundant evidence consumes budget."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,ROTOR,BLADE,PROBE,EVIDENCE,COST,CHOICE,BAD=12,3,4,9,10,15,11,14,8
LEVELS=[{"name":"Direct Wake","model":1,"tests":(1,),"budget":1},{"name":"Shared Rotor","model":2,"tests":(2,1),"budget":2},{"name":"Coincident Blade","model":3,"tests":(1,3,2),"budget":3},{"name":"Reset Contrast","model":2,"tests":(3,4,1,2),"budget":4},{"name":"Costly Repeat","model":3,"tests":(2,1,4,3,2),"budget":6},{"name":"Impeller Probe","model":1,"tests":(1,4,3,2,4,1),"budget":7}]
def result(model,side,a):return (model*a+side*(model+2))%4
def required(x):
 side=0;out=[]
 for a in x["tests"]:
  if a==4:side=1-side
  else:out.append((side,a,result(x["model"],side,a)))
 return tuple(out)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  for i in range(2):x=10+i*31;f[10:36,x:x+22]=ROTOR;f[17:29,x+8:x+14]=BLADE
  f[7:10,10+g.side*31:32+g.side*31]=PROBE
  for i,(_,_,v) in enumerate(g.evidence[-8:]):f[41+i*2:43+i*2,7:7+v*12]=EVIDENCE
  f[55:58,7:7+g.cost*7]=COST;f[59:61,7:7+g.choice*13]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q283(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.side=0;self.evidence=[];self.cost=self.choice=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q283",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.side=0;self.evidence=[];self.cost=self.choice=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   item=(self.side,a,result(x["model"],self.side,a));self.cost+=2 if item in self.evidence else 1;self.evidence.append(item)
   if self.cost>x["budget"]:self.bad=True;self.lose()
  elif a==4:self.side=1-self.side
  elif a==5:self.choice=(self.choice+1)%4
  elif a==6:
   if tuple(self.evidence)==required(x) and self.choice==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
