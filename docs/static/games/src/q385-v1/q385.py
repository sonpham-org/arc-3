"""q385 Alloy Delegation -- integrate controller marks expressed in a moving foundry frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,BILLET,VIEW,MARK,FRAME,INTEGRATE,BAD=6,10,9,14,12,5,11,7,15
LEVELS=[{"name":"Split Force","plan":(1,3,4,2,3,5)},{"name":"Remote Billet","plan":(2,3,4,1,3,5)},{"name":"Rotated Marks","plan":(1,2,3,4,2,3,5)},{"name":"Moving Handoff","plan":(2,1,3,4,1,2,3,5)},{"name":"Translated Relay","plan":(1,3,4,2,1,3,4,2,3,5)},{"name":"Alloy Delegation","plan":(2,1,3,4,1,3,4,2,3,5)}]
def advance(s,a):
 controller,views,marks,rotation,offset,integrated=s;views=list(views);marks=list(marks)
 if a in (1,2):views[controller]|=1<<((controller+a+rotation+offset)%4)
 elif a==3:marks[controller]=(views[controller]*3+rotation+offset+controller)%8
 elif a==4:controller=1-controller;rotation=(rotation+1)%4;offset=(offset+1)%5
 elif a==5:integrated=(marks[0]^marks[1]^rotation^offset)%8
 return controller,tuple(views),tuple(marks),rotation,offset,integrated
def target(x):
 s=(0,(0,0),(0,0),0,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY;f[8:15,8:56]=LANE
  for i,v in enumerate(g.views):x=7+i*28;f[20:39,x:x+22]=BILLET-i;f[24:31,x+4:x+4+max(1,v)*3]=VIEW;f[42:45,x:x+max(1,g.marks[i])*3]=MARK
  f[50:53,8:11+g.controller*22]=INTEGRATE;f[54:57,8:11+g.rotation*11]=FRAME;f[58:60,8:11+g.offset*9]=FRAME
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q385(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q385",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.views=(0,0);self.marks=(0,0);self.rotation=self.offset=self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.controller,self.views,self.marks,self.rotation,self.offset,self.integrated=advance((self.controller,self.views,self.marks,self.rotation,self.offset,self.integrated),a)
  elif a==6:
   if (self.controller,self.views,self.marks,self.rotation,self.offset,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
