"""q282 Semaphore Probe -- join causal signatures from two miniature signal systems."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,MAST,FLAG,BEAM,MINI,EVIDENCE,CHOICE,BAD=15,1,12,14,10,6,11,9,8
LEVELS=[
 {"name":"Direct Relay","model":1,"a":(1,),"b":(2,),"budget":2},
 {"name":"Shared Mast","model":2,"a":(2,1),"b":(3,),"budget":3},
 {"name":"Coincident Flag","model":3,"a":(1,3),"b":(2,1),"budget":4},
 {"name":"Two Miniatures","model":2,"a":(3,2,1),"b":(1,3),"budget":5},
 {"name":"Policy Test","model":3,"a":(2,1,3),"b":(3,1,2),"budget":6},
 {"name":"Semaphore Probe","model":1,"a":(1,2,3,1),"b":(2,3,1,2),"budget":8}]
def result(model,mini,a):return (model*a+mini*(model+1)+a//2)%4
def required(x):return tuple((0,a,result(x["model"],0,a)) for a in x["a"])+tuple((1,a,result(x["model"],1,a)) for a in x["b"])
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=YARD
  for i in range(3):x=9+i*18;f[10:43,x:x+3]=MAST;f[12+i*7:20+i*7,x+3:x+13]=FLAG
  f[7:10,8+g.mini*25:28+g.mini*25]=MINI
  for i,(_,_,v) in enumerate(g.evidence[-8:]):f[44+i*2:46+i*2,7:7+v*12]=EVIDENCE
  f[57:60,8:8+g.choice*13]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q282(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mini=0;self.evidence=[];self.choice=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q282",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mini=0;self.evidence=[];self.choice=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   self.evidence.append((self.mini,a,result(x["model"],self.mini,a)))
   if len(self.evidence)>x["budget"]:self.bad=True;self.lose()
  elif a==4:self.mini=1-self.mini
  elif a==5:self.choice=(self.choice+1)%4
  elif a==6:
   if tuple(self.evidence)==required(x) and self.choice==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
