"""q281 Pollen Probe -- distinguish causes before and after a complemented wear boundary."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,KITE,WAVE,EVIDENCE,WEAR,CHOICE,TARGET,BAD=14,10,7,11,15,12,9,0,8
LEVELS=[
 {"name":"Direct Bloom","model":1,"before":(1,),"after":(2,)},
 {"name":"Shared Wind","model":2,"before":(2,1),"after":(3,)},
 {"name":"Coincident Kite","model":3,"before":(1,3),"after":(2,1)},
 {"name":"Wear Boundary","model":2,"before":(3,2,1),"after":(1,3)},
 {"name":"Complement Wave","model":3,"before":(2,1,3),"after":(3,1,2)},
 {"name":"Pollen Probe","model":1,"before":(1,2,3,1),"after":(2,3,1,2)}]
def signature(model,a,worn):
 v=(model*a+a//2)%4
 return 3-v if worn else v
def expected(x):return tuple((a,signature(x["model"],a,False)) for a in x["before"])+tuple((a,signature(x["model"],a,True)) for a in x["after"])
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[6:58,4:60]=MEADOW
  for i in range(3):
   x=10+i*17;f[12:20,x:x+9]=KITE;f[20:38,x+3:x+6]=WAVE
  for i,(_,v) in enumerate(g.evidence[-8:]):f[43+i*2:45+i*2,7:7+v*12]=EVIDENCE
  if g.worn:f[8:11,8:56]=WEAR
  f[53:55,8:8+LEVELS[g.level_index]["model"]*14]=TARGET;f[56:59,8:8+g.choice*14]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q281(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.evidence=[];self.worn=False;self.choice=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q281",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.evidence=[];self.worn=False;self.choice=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.evidence.append((a,signature(x["model"],a,self.worn)))
  elif a==4:self.worn=True
  elif a==5:self.choice=(self.choice+1)%4
  elif a==6:
   if tuple(self.evidence)==expected(x) and self.worn and self.choice==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
