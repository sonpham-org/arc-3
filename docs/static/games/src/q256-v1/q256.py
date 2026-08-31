"""q256 Crossing Pact -- infer a convention from offers distributed across controllers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,DOCK,PASSENGER,OFFER,REPLY,MARK,CONTROL,BAD=6,10,9,14,5,4,11,2,15
LEVELS=[{"name":"Fair Fare","rule":1,"plan":(1,4,5)},{"name":"Recent Dock","rule":2,"plan":(2,4,5,1,4,5)},{"name":"Reciprocal Crossing","rule":3,"plan":(1,3,4,5,2,4,5,1,4,5)},{"name":"Split Convention","rule":2,"plan":(3,1,4,5,2,4,5)},{"name":"Remote Courtesy","rule":3,"plan":(2,4,5,1,3,4,5,2,4,5)},{"name":"Crossing Pact","rule":1,"plan":(1,2,3,4,5)}]
def response(rule,a,last,controller,mark):return (rule+a+last+controller+mark)%4
def advance(s,a,x):
 evidence,last,controller,marks,choice=s;evidence=list(evidence);marks=list(marks)
 if a in (1,2,3):evidence.append((controller,a,response(x["rule"],a,last,controller,marks[controller])));last=a
 elif a==4:marks[controller]=(last+controller+len(evidence))%4
 elif a==5:controller=1-controller;choice=(choice+1)%4
 return tuple(evidence),last,controller,tuple(marks),choice
def target(x):
 s=((),0,0,(0,0),0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=RIVER
  for i in range(2):x=8+i*29;f[9:31,x:x+22]=DOCK;f[15:23,x+6:x+16]=PASSENGER-i
  for i,(_,_,v) in enumerate(g.evidence[-6:]):f[35+i*3:37+i*3,8:11+v*11]=REPLY
  f[32:34,8:20]=OFFER;f[52:55,8:11+g.marks[g.controller]*11]=MARK;f[57:60,8:11+g.controller*22]=CONTROL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q256(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q256",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.last=self.controller=self.choice=0;self.marks=(0,0)
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.evidence,self.last,self.controller,self.marks,self.choice=advance((self.evidence,self.last,self.controller,self.marks,self.choice),a,x)
  elif a==6:
   if (self.evidence,self.last,self.controller,self.marks,self.choice)==self.target and self.choice==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
