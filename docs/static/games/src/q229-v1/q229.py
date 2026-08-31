"""q229 Monsoon Veil -- schedule attention across rain cells on two unequal cycles."""
from copy import deepcopy
from math import lcm
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,FOCUS,CYCLEA,CYCLEB,GOAL,BAD=0,10,9,14,6,11,4,7,15
def routine(n):return tuple((i%4)+1 for i in range(n))+(5,)
LEVELS=[{"name":"Paired Shower","periods":(2,2),"plan":routine(2)},{"name":"Triple Cell","periods":(3,3),"plan":routine(3)},{"name":"Nested Rain","periods":(2,4),"plan":routine(4)},{"name":"Unequal Fronts","periods":(2,3),"plan":routine(6)},{"name":"Long Forecast","periods":(3,4),"plan":routine(12)},{"name":"Monsoon Veil","periods":(4,5),"plan":routine(20)}]
def advance(s,a,x):
 seeds,focus,pa,pb,history,synced=s;seeds=list(seeds);history=list(history)
 if a in (1,2,3,4):
  focus=(focus+(1 if a==4 else a))%3
  for i in range(3):
   if i!=focus:seeds[i]=(seeds[i]+a+pa+pb+i)%6
  history.append((a,focus));pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or not history:return None
  synced=(tuple(seeds),focus,len(history));history=[]
 return tuple(seeds),focus,pa,pb,tuple(history),synced
def target(x):
 s=((0,2,4),0,0,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i,v in enumerate(g.seeds):x=8+i*18;f[8:34,x:x+14]=CLOUD;f[12+v*3:17+v*3,x+4:x+10]=RAIN-i
  f[6:9,8+g.focus*18:22+g.focus*18]=FOCUS;f[40:43,8:11+g.pa*9]=CYCLEA;f[47:50,8:11+g.pb*9]=CYCLEB;f[54:57,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q229(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q229",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.seeds=(0,2,4);self.focus=self.pa=self.pb=0;self.history=();self.synced=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.seeds,self.focus,self.pa,self.pb,self.history,self.synced),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.seeds,self.focus,self.pa,self.pb,self.history,self.synced=s
  elif a==6:
   if (self.seeds,self.focus,self.pa,self.pb,self.history,self.synced)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
