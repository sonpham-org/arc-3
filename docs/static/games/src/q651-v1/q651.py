"""q651 Aurora Analogy -- transfer a curtain relation into mote coordination."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,SOURCE,RELATION,HYSTERESIS,TARGET,BAD=4,10,12,14,6,11,5,7,15
LEVELS=[{"name":"One Relation","rule":1,"plan":(1,2,4,3,5)},{"name":"Shifted Surface","rule":2,"plan":(2,3,1,4,2,5)},{"name":"Mote Transfer","rule":3,"plan":(1,3,2,4,1,2,5)},{"name":"Hysteretic Return","rule":1,"plan":(2,1,4,3,2,1,5)},{"name":"Crossed Analogy","rule":2,"plan":(1,2,3,4,3,1,2,5)},{"name":"Aurora Analogy","rule":3,"plan":(3,1,2,1,4,2,3,1,2,5)}]
def advance(s,a,x):
 source,relation,hyst,target,result=s;source=list(source);target=list(target)
 if a in (1,2,3):
  if relation is None:source.append((a,(a*x["rule"]+len(source))%5))
  else:target.append((a,(a+x["rule"]+hyst+len(target))%5))
 elif a==4:
  if relation is not None or len(source)<2:return None
  relation=(x["rule"],tuple((b-a)%5 for (_,a),(_,b) in zip(source,source[1:])),len(source));hyst=(hyst+len(source)+x["rule"])%5
 elif a==5:
  if relation is None or not target:return None
  result=(relation,tuple(target),hyst,sum(v for _,v in target)%6)
 return tuple(source),relation,hyst,tuple(target),result
def target_state(x):
 s=((),None,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:29]=CURTAIN;f[8:31,35:57]=MOTE
  for i,(_,v) in enumerate(g.source[-4:]):f[12+i*4:15+i*4,10:13+v*3]=SOURCE
  for i,(_,v) in enumerate(g.target[-4:]):f[12+i*4:15+i*4,38:41+v*3]=TARGET
  f[37:40,8:24]=RELATION if g.relation else SOURCE;f[45:48,8:11+g.hyst*9]=HYSTERESIS;f[55:58,40:56]=TARGET if g.result else MOTE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q651(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target_state=target_state(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q651",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=();self.relation=None;self.hyst=0;self.target=();self.result=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target_state=target_state(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.source,self.relation,self.hyst,self.target,self.result),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.source,self.relation,self.hyst,self.target,self.result=s
  elif a==6:
   if (self.source,self.relation,self.hyst,self.target,self.result)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
