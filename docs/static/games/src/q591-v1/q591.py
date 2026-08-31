"""q591 Aurora Grammar -- compose grouped mote commands through hysteretic relays."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,TOKEN,RELAY,HYSTERESIS,RESULT,BAD=2,10,12,14,6,4,11,7,15
LEVELS=[{"name":"One Relay","plan":(1,2,4,5)},{"name":"Grouped Tokens","plan":(2,3,1,4,5)},{"name":"Second Relay","plan":(1,2,4,3,4,5)},{"name":"Nested Phrase","plan":(3,1,2,4,2,1,4,5)},{"name":"Hysteretic Grammar","plan":(1,3,4,2,3,1,4,5)},{"name":"Aurora Grammar","plan":(3,1,2,4,1,3,4,2,5)}]
def advance(s,a):
 tokens,relay,hyst,groups,result=s;tokens=list(tokens);groups=list(groups)
 if a in (1,2,3):tokens.append((a,(a+relay+hyst+len(tokens))%4))
 elif a==4:
  if not tokens:return None
  transformed=tuple((a,(v+relay+hyst+i)%4) for i,(a,v) in enumerate(tokens));groups.append(transformed);tokens=[];relay=(relay+1)%3;hyst=(hyst+relay+len(groups))%5
 elif a==5:
  if not groups:return None
  result=(tuple(groups),relay,hyst,sum(v for grp in groups for _,v in grp)%7)
 return tuple(tokens),relay,hyst,tuple(groups),result
def target(x):
 s=((),0,0,(),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:57]=CURTAIN
  for i,(a,v) in enumerate(g.tokens[-6:]):x=9+i*8;f[12:19,x:x+6]=TOKEN-a;f[21:25,x:x+3+v]=MOTE-v
  f[36:39,8:11+g.relay*14]=RELAY;f[43:46,8:11+g.hyst*9]=HYSTERESIS;f[53:56,40:56]=RESULT if g.result else CURTAIN
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q591(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q591",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tokens=();self.relay=self.hyst=0;self.groups=();self.result=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tokens,self.relay,self.hyst,self.groups,self.result),a)
   if s is None:self.bad=True;self.lose()
   else:self.tokens,self.relay,self.hyst,self.groups,self.result=s
  elif a==6:
   if (self.tokens,self.relay,self.hyst,self.groups,self.result)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
