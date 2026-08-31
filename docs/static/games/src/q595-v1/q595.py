"""q595 Alloy Grammar -- compose local symbols before decoding in a transformed frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,GLYPH,GROUP,RELATION,RELAY,FRAME,OUTPUT,BAD=6,1,9,4,11,2,13,7,15
LEVELS=[
 {"name":"Grouped Signal","plan":(1,3,5)},{"name":"Relative Signal","plan":(2,3,5)},
 {"name":"Rotated Message","plan":(4,1,3,5)},{"name":"Composed Relay","plan":(1,2,4,3,5)},
 {"name":"Moving Syntax","plan":(4,1,2,4,3,5)},{"name":"Alloy Grammar","plan":(1,4,2,3,4,1,3,5)}]
def advance(s,a,x):
 group,relation,relay,origin,rotation,output=s
 if a==1:group=(group+1)%4
 elif a==2:relation=(relation+1)%3
 elif a==3:relay=(relay+group+relation+rotation+1)%5
 elif a==4:origin=(origin+1)%6;rotation=(rotation+1)%4
 elif a==5:output=(relay+origin+rotation,group,relation)
 return group,relation,relay,origin,rotation,output
def target(x):
 s=(0,0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY
  for i in range(3):x=8+i*17;f[8:22,x:x+12]=GLYPH+i
  f[11:18,9:13+g.group*2]=GROUP;f[11:18,26:30+g.relation*3]=RELATION;f[11:18,43:47+g.relay*2]=RELAY
  f[29:33,8:8+g.origin*8]=FRAME;f[36:40,8:8+g.rotation*11]=RELATION;f[45:49,8:56]=RELAY
  if g.output:f[52:57,38:56]=OUTPUT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q595(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q595",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.group=self.relation=self.relay=self.origin=self.rotation=0;self.output=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.group,self.relation,self.relay,self.origin,self.rotation,self.output=advance((self.group,self.relation,self.relay,self.origin,self.rotation,self.output),a,self.cfg)
  elif a==6:
   if (self.group,self.relation,self.relay,self.origin,self.rotation,self.output)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
